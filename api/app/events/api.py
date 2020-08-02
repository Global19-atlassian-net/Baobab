from datetime import datetime
import traceback

from flask import g, request
import flask_restful as restful
from flask_restful import reqparse, fields, marshal_with
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.email_template.repository import EmailRepository as email_repository
from app.events.models import Event, EventRole
from app.events.mixins import EventsMixin, EventsKeyMixin, EventMixin
from app.users.models import AppUser
from app.users.repository import UserRepository as user_repository
from app.applicationModel.models import ApplicationForm
from app.responses.models import Response
from app.responses.repository import ResponseRepository as response_repository
from app.registration.repository import OfferRepository as offer_repository
from app.registration.repository import RegistrationRepository as registration_repository
from app.guestRegistrations.repository import GuestRegistrationRepository as guest_registration_repository

from app import db, bcrypt, LOGGER
from app.utils.errors import EVENT_NOT_FOUND, FORBIDDEN, EVENT_WITH_KEY_NOT_FOUND, EVENT_KEY_IN_USE

from app.utils.auth import auth_optional, auth_required, event_admin_required
from app.utils.emailer import send_mail
from app.events.repository import EventRepository as event_repository
from app.organisation.models import Organisation
from app.events.models import EventType
import app.events.status as event_status
from app.reviews.repository import ReviewRepository as review_repository
from app.reviews.repository import ReviewConfigurationRepository as review_config_repository

def status_info(status):
    if status is None:
        return None

    return {
        'invited_guest': status.invited_guest,
        'application_status': status.application_status,
        'registration_status': status.registration_status,
        'offer_status': status.offer_status,
        'outcome_status': status.outcome_status,
        'is_event_attendee': status.is_event_attendee
    }

def event_info(user_id, event_org, status):
    return {
        'id': event_org.Event.id,
        'name': event_org.Event.name,
        'description': event_org.Event.description,
        'key': event_org.Event.key,
        'start_date': event_org.Event.start_date.strftime("%d %B %Y"),
        'end_date': event_org.Event.end_date.strftime("%d %B %Y"),
        'status': status_info(status),
        'email_from': event_org.Event.email_from,
        'organisation_name': event_org.Organisation.name,
        'organisation_id': event_org.Organisation.id,
        'url': event_org.Event.url,
        'event_type': event_org.Event.event_type.value.upper(),
        'is_application_open': event_org.Event.is_application_open,
        'is_application_opening': event_org.Event.is_application_opening,
        'is_review_open': event_org.Event.is_review_open,
        'is_review_opening': event_org.Event.is_review_opening,
        'is_selection_open': event_org.Event.is_selection_open,
        'is_selection_opening': event_org.Event.is_selection_opening,
        'is_offer_open': event_org.Event.is_offer_open,
        'is_offer_opening': event_org.Event.is_offer_opening,
        'is_registration_open': event_org.Event.is_registration_open,
        'is_registration_opening': event_org.Event.is_registration_opening,
        'is_event_open': event_org.Event.is_event_open,
        'is_event_opening': event_org.Event.is_event_opening,
        'travel_grant': event_org.Event.travel_grant,
        "miniconf_url": event_org.Event.miniconf_url
    }


event_fields = {
    'id': fields.Integer,
    'name': fields.Raw(attribute=lambda event: event.get_all_name_translations()),
    'description': fields.Raw(attribute=lambda event: event.get_all_description_translations()),
    'key': fields.String,
    'start_date': fields.DateTime(dt_format='iso8601'),
    'end_date': fields.DateTime(dt_format='iso8601'),
    'email_from': fields.String,
    'organisation_name': fields.String(attribute='organisation.name'),
    'organisation_id': fields.String(attribute='organisation.id'),
    'url': fields.String,
    'application_open': fields.DateTime(dt_format='iso8601'),
    'application_close': fields.DateTime(dt_format='iso8601'),
    'review_open': fields.DateTime(dt_format='iso8601'),
    'review_close': fields.DateTime(dt_format='iso8601'),
    'selection_open': fields.DateTime(dt_format='iso8601'),
    'selection_close': fields.DateTime(dt_format='iso8601'),
    'offer_open': fields.DateTime(dt_format='iso8601'),
    'offer_close': fields.DateTime(dt_format='iso8601'),
    'registration_open': fields.DateTime(dt_format='iso8601'),
    'registration_close': fields.DateTime(dt_format='iso8601'),
}


def get_user_event_response_status(user_id, event_id):

    def _log_application_status(context):
        LOGGER.debug("Application {} for user_id: {}, event_id: {}".format(
            context, user_id, event_id))

    try:
        applicationForm = db.session.query(ApplicationForm).filter(
            ApplicationForm.event_id == event_id).first()

        if applicationForm:
            if applicationForm.event.application_close < datetime.now():
                _log_application_status('closed, deadline passed')
                return "Application closed"
            elif user_id:
                response = db.session.query(Response).filter(
                    Response.application_form_id == applicationForm.id).filter(
                        Response.user_id == user_id
                ).order_by(Response.started_timestamp.desc()).first()

                if response:
                    if response.is_withdrawn:
                        _log_application_status('withdrawn')
                        return "Application withdrawn"
                    elif response.is_submitted:
                        _log_application_status('submitted')
                        return "Applied"
                    else:
                        _log_application_status('continue')
                        return "Continue application"
                else:
                    _log_application_status('open')
                    return "Apply now"

            else:
                _log_application_status('open')
                return "Apply now"

    except SQLAlchemyError as e:
        LOGGER.error("Database error encountered: {}".format(e))
    except:
        LOGGER.error("Encountered unknown error: {}".format(
            traceback.format_exc()))

    _log_application_status('not available')
    return "Application not available"


class EventAPI(EventMixin, restful.Resource):
    @auth_required
    @marshal_with(event_fields)
    def get(self):
        event_id = request.args['id']
        event = event_repository.get_by_id(event_id)
        if not event:
            return EVENT_NOT_FOUND
        return event

    @auth_required
    @marshal_with(event_fields)
    def post(self):
        args = self.req_parser.parse_args()

        user_id = g.current_user["id"]
        current_user = user_repository.get_by_id(user_id)
        if not current_user.is_admin:
            return FORBIDDEN

        _date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        name = args['name']
        description = args['description']
        start_date = datetime.strptime(
            (args['start_date']), _date_format)
        end_date = datetime.strptime(
            (args['end_date']), _date_format)
        key = args['key']
        organisation_id = args['organisation_id']
        email_from = args['email_from']
        url = args['url']
        application_open = datetime.strptime(
            (args['application_open']), _date_format)
        application_close = datetime.strptime(
            (args['application_close']), _date_format)
        review_open = datetime.strptime(
            (args['review_open']), _date_format)
        review_close = datetime.strptime(
            (args['review_close']), _date_format)
        selection_open = datetime.strptime(
            (args['selection_open']), _date_format)
        selection_close = datetime.strptime(
            (args['selection_close']), _date_format)
        offer_open = datetime.strptime(
            (args['offer_open']), _date_format)
        offer_close = datetime.strptime(
            (args['offer_close']), _date_format)
        registration_open = datetime.strptime(
            (args['registration_open']), _date_format)
        registration_close = datetime.strptime(
            (args['registration_close']), _date_format)
        event_type = args['event_type'].upper()

        event = Event(
            name,
            description,
            start_date,
            end_date,
            key,
            organisation_id,
            email_from,
            url,
            application_open,
            application_close,
            review_open,
            review_close,
            selection_open,
            selection_close,
            offer_open,
            offer_close,
            registration_open,
            registration_close,
            EventType[event_type],
            travel_grant=False   # TODO: Add to incoming request
        )
        event.add_event_role('admin', user_id)
        try:
            event = event_repository.add(event)
        except IntegrityError as e:

            LOGGER.error("Event with KEY: {} already exists".format(key))
            LOGGER.error(e)
            return EVENT_KEY_IN_USE

        event = event_repository.get_by_id(event.id)
        return event, 201

    @auth_required
    @marshal_with(event_fields)
    def put(self):
        args = self.req_parser.parse_args()

        event = event_repository.get_by_id(args['id'])
        if not event:
            return EVENT_NOT_FOUND

        user_id = g.current_user["id"]
        current_user = user_repository.get_by_id(user_id)
        if not current_user.is_event_admin(event.id):
            return FORBIDDEN

        _date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        name = args['name']
        description = args['description']
        start_date = datetime.strptime(
            (args['start_date']), _date_format)
        end_date = datetime.strptime(
            (args['end_date']), _date_format)
        key = args['key']
        organisation_id = args['organisation_id']
        email_from = args['email_from']
        url = args['url']
        application_open = datetime.strptime(
            (args['application_open']), _date_format)
        application_close = datetime.strptime(
            (args['application_close']), _date_format)
        review_open = datetime.strptime(
            (args['review_open']), _date_format)
        review_close = datetime.strptime(
            (args['review_close']), _date_format)
        selection_open = datetime.strptime(
            (args['selection_open']), _date_format)
        selection_close = datetime.strptime(
            (args['selection_close']), _date_format)
        offer_open = datetime.strptime(
            (args['offer_open']), _date_format)
        offer_close = datetime.strptime(
            (args['offer_close']), _date_format)
        registration_open = datetime.strptime(
            (args['registration_open']), _date_format)
        registration_close = datetime.strptime(
            (args['registration_close']), _date_format)

        event.update(
            name,
            description,
            start_date,
            end_date,
            key,
            organisation_id,
            email_from,
            url,
            application_open,
            application_close,
            review_open,
            review_close,
            selection_open,
            selection_close,
            offer_open,
            offer_close,
            registration_open,
            registration_close
        )

        try:
            db.session.commit()
        except IntegrityError:
            LOGGER.error("Event with KEY: {} already exists".format(key))
            return EVENT_KEY_IN_USE

        event = event_repository.get_by_id(event.id)
        return event, 200


class EventsAPI(restful.Resource):

    @auth_required
    def get(self):
        user_id = g.current_user["id"]

        events = event_repository.get_upcoming_for_organisation(g.organisation.id)
        returnEvents = []

        for event in events:
            status = None if user_id == 0 else event_status.get_event_status(event.Event.id, user_id)
            returnEvents.append(event_info(user_id, event, status))

        return returnEvents, 200


def _process_timeseries(timeseries):
    timeseries = [
            (d.strftime('%Y-%m-%d'), c) for (d, c) in timeseries
            if d is not None
        ]
    return timeseries

def _combine_timeseries(first_timeseries, second_timeseries):
    output = []
    i, j = 0, 0
    while i < len(first_timeseries) and j < len(second_timeseries):
        first_date, first_count = first_timeseries[i]
        second_date, second_count = second_timeseries[j]
        if first_date == second_date:
            output.append((first_date, first_count + second_count))
            i += 1
            j += 1
        if first_date < second_date:
            output.append((first_date, first_count))
            i += 1
        else:
            output.append((second_date, second_count))

    while i < len(first_timeseries):
        output.append(first_timeseries[i])
        i += 1

    while j < len(second_timeseries):
        output.append(second_timeseries[j])
        j += 1

    return output


class EventStatsAPI(EventsMixin, restful.Resource):

    @event_admin_required
    def get(self, event_id):
        event = event_repository.get_by_id_with_organisation(event_id)
        if not event:
            return EVENT_NOT_FOUND

        num_responses = response_repository.get_total_count_by_event(event_id)
        num_submitted_respones = response_repository.get_submitted_count_by_event(event_id)
        num_withdrawn_responses = response_repository.get_withdrawn_count_by_event(event_id)
        submitted_response_timeseries = _process_timeseries(response_repository.get_submitted_timeseries_by_event(event_id))

        review_config = review_config_repository.get_configuration_for_event(event_id)
        required_reviews = 1 if review_config is None else review_config.num_reviews_required
        reviews_completed = review_repository.get_count_reviews_completed_for_event(event_id)
        reviews_incomplete = review_repository.get_count_reviews_incomplete_for_event(event_id)
        reviews_unallocated = review_repository.count_unassigned_reviews(event_id, required_reviews)
        reviews_timeseries = _process_timeseries(review_repository.get_review_complete_timeseries_by_event(event_id))

        offers_allocated = offer_repository.count_offers_allocated(event_id)
        offers_accepted = offer_repository.count_offers_accepted(event_id)
        offers_rejected = offer_repository.count_offers_rejected(event_id)
        offers_timeseries = _process_timeseries(offer_repository.timeseries_offers_accepted(event_id))

        num_registrations = registration_repository.count_registrations(event_id)
        num_guests = guest_registration_repository.count_guests(event_id)
        num_registered_guests = guest_registration_repository.count_registered_guests(event_id)
        registration_timeseries = _process_timeseries(registration_repository.timeseries_registrations(event_id))
        guest_registration_timeseries = _process_timeseries(guest_registration_repository.timeseries_guest_registrations(event_id))
        registration_timeseries = _combine_timeseries(registration_timeseries, guest_registration_timeseries)

        return {
            'num_responses': num_responses,
            'num_submitted_responses': num_submitted_respones,
            'num_withdrawn_responses': num_withdrawn_responses,
            'submitted_timeseries': submitted_response_timeseries,
            'reviews_completed': reviews_completed,
            'review_incomplete': reviews_incomplete,
            'reviews_unallocated': reviews_unallocated,
            'reviews_complete_timeseries': reviews_timeseries,
            'offers_allocated': offers_allocated,
            'offers_accepted': offers_accepted,
            'offers_rejected': offers_rejected,
            'offers_accepted_timeseries': offers_timeseries,
            'num_registrations': num_registrations,
            'num_guests': num_guests,
            'num_registered_guests': num_registered_guests,
            'registration_timeseries': registration_timeseries
        }, 200


class EventsByKeyAPI(EventsKeyMixin, restful.Resource):

    @auth_required
    def get(self):
        args = self.req_parser.parse_args()

        user_id = g.current_user['id']

        event = event_repository.get_by_key_with_organisation(
            args['event_key'])
        if not event:
            return EVENT_WITH_KEY_NOT_FOUND
        info = event_info(
            g.current_user['id'], 
            event, 
            event_status.get_event_status(event.Event.id, user_id))
        return info, 200


class NotSubmittedReminderAPI(EventsMixin, restful.Resource):

    @auth_required
    def post(self):
        args = self.req_parser.parse_args()
        event_id = args['event_id']
        user_id = g.current_user['id']

        event = db.session.query(Event).get(event_id)
        if not event:
            return EVENT_NOT_FOUND

        current_user = user_repository.get_by_id(user_id)
        if not current_user.is_event_admin(event_id):
            return FORBIDDEN

        users = user_repository.get_all_with_unsubmitted_response()
        for user in users:
            title = user.user_title
            firstname = user.firstname
            lastname = user.lastname
            event_name = event.name
            organisation_name = event.organisation.name
            deadline = event.application_close.strftime('%A %-d %B %Y')

            subject = 'FINAL REMINDER to submit you application for {}'.format(
                event_name)
            not_submitted_body = email_repository.get(event_id, 'application-not-submitted').template
            body = not_submitted_body.format(
                title=title,
                firstname=firstname,
                lastname=lastname,
                event=event_name,
                organisation_name=organisation_name,
                deadline=deadline)

            send_mail(recipient=user.email, subject=subject, body_text=body)

        return {'unsubmitted_responses': len(users)}, 201


class NotStartedReminderAPI(EventsMixin, restful.Resource):

    @auth_required
    def post(self):
        args = self.req_parser.parse_args()
        event_id = args['event_id']
        user_id = g.current_user['id']

        event = db.session.query(Event).get(event_id)
        if not event:
            return EVENT_NOT_FOUND

        current_user = user_repository.get_by_id(user_id)
        if not current_user.is_event_admin(event_id):
            return FORBIDDEN

        users = user_repository.get_all_without_responses()
        for user in users:
            title = user.user_title
            firstname = user.firstname
            lastname = user.lastname
            event_name = event.name
            organisation_name = event.organisation.name
            system_name = event.organisation.system_name
            deadline = event.application_close.strftime('%A %-d %B %Y')

            not_started_body = email_repository.get(event_id, 'application-not-started').template
            subject = 'FINAL REMINDER: We do not have your application to attend {}'.format(
                event_name)
            body = not_started_body.format(
                title=title,
                firstname=firstname,
                lastname=lastname,
                event=event_name,
                organisation_name=organisation_name,
                system_name=system_name,
                deadline=deadline)

            send_mail(recipient=user.email, subject=subject, body_text=body)

        return {'not_started_responses': len(users)}, 201
