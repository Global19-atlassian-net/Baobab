from app import db


class EmailTemplate(db.Model):

    __tablename__ = 'email_template'
    __table_args__ = tuple([db.UniqueConstraint('key', 'event_id', 'language', name='uq_email_template_key_event_id')])

    id = db.Column(db.Integer(), primary_key=True)
    key = db.Column(db.String(50), nullable=False)
    event_id = db.Column(db.Integer(), db.ForeignKey('event.id'), nullable=True)
    language = db.Column(db.String(2), nullable=False)
    template = db.Column(db.String(), nullable=False)
    subject = db.Column(db.String(), nullable=False)

    event = db.relationship('Event', foreign_keys=[event_id])

    def __init__(self, key, event_id, subject, template, language):
        self.key = key
        self.event_id = event_id
        self.subject = subject
        self.template = template
        self.language = language
