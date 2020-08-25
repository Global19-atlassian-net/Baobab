import React, { Component } from "react";
import FormGroup from "./FormGroup";
import MultiFileComponent from './MultiFileComponent';
import "./Style.css";


class FormMultiFile extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            fileList: [{ name: null, file: null, delete: null, filePath: null }],
            addError: false,
        }
    }

    componentWillMount() {
        if (this.props.value) {
            this.setState({
                fileList: this.props.value,
            })
        }
    }


    // add file
    addFile = () => {
        // check against empty fields
        let condition = handleList.all(val => val.file);

        // variables
        let addError = condition ? false : true;
        let handleList = this.state.fileList;

        // add item if there is no empty fields
        if (condition) {
            handleList.push({ name: null, file: null, delete: null, filePath: null })
        }

        this.setState({
            addError: addError,
            fileList: handleList
        }, () => {
            condition = true;
            addError = false
        })
    }

    del = (file, del) => {
        let handleList = this.state.fileList;

        if (del) {
            if (handleList.length > 1) {
                // del file
                let filteredList = handleList.filter((val) => {
                    return file != val.file
                })
                handleList = filteredList
            }
            else {
                handleList = []
            }
        }

        // setState and Callback functions
        this.setState({
            fileList: handleList,
        },  // reset function variables
            () => {
                this.props.onChange(handleList)
            })
    }


    //handle upload
    handleUpload = (file, name, del, filePath) => {
        // function variables
        let handleDuplicates = false;
        let handleList = this.state.fileList;

        // Add new value
        handleList.map(val => {
            if (!val.file) {
                val.name = name;
                val.file = file;
                val.delete = del;
                val.filePath = filePath;
            }
            // test for and handle updated values
            else if (val.file == file) {
                val.name = name;
                val.delete = del;
                val.filePath = filePath;
                handleDuplicates = true
            }
        })

        // setState and Callback functions
        this.setState({
            fileList: handleList,
        },  // reset function variables
            () => {
                if (!handleDuplicates) {
                    this.props.uploadFile(file, handleList)
                }
                handleDuplicates = false;
            })
    }



    render() {

        return (
            <div>
                <FormGroup>
                    {this.state.fileList.map(val => {
                        return <MultiFileComponent className="multi-file-component"
                            handleUpload={(file, name, del, filePath) => this.handleUpload(file, name, del, filePath)}
                            errorText={this.props.errorText}
                            addError={this.state.addError}
                            del={(file) => this.del(file)}
                            value={val}
                        />
                    })}

                    <button className="add-file-btn" onClick={(e) => this.addFile(e)}>Add File</button>
                    <div className={this.props.errorText ? "errorText display" : "errorText"}> <p>{this.props.errorText}</p> </div>
                </FormGroup>
            </div>
        );
    }

}
export default FormMultiFile;
