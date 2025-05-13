// Copyright 2021 Red Hat, Inc
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { connect, useDispatch } from 'react-redux'

import {
    Button,
    Modal,
    ModalVariant,
    Form,
    FormGroup,
    TextInput
} from '@patternfly/react-core'

import { autohold } from '../../api'
import { addAutoholdError } from '../../actions/adminActions'
import { addNotification } from '../../actions/notifications'
import { fetchAutoholds } from '../../actions/autoholds'

const AutoholdModal = props => {

    const dispatch = useDispatch()
    const { tenant, user, showAutoholdModal, setShowAutoholdModal } = props

    const [change, setChange] = useState('')
    const [changeRef, setChangeRef] = useState('')
    const [project, setProject] = useState('some project')
    const [job_name, setJob_name] = useState('some job')
    const [reason, setReason] = useState('-')
    const [count, setCount] = useState(1)
    const [nodeHoldExpiration, setNodeHoldExpiration] = useState(86400)

    // Override defaults if optional parameters were passed
    useEffect(() => {
        if (props.change) { setChange(props.change) }
        if (props.changeRef) { setChangeRef(props.changeRef) }
        if (props.project) { setProject(props.project) }
        if (props.jobName) { setJob_name(props.jobName) }
        if (props.reason) {
            setReason(props.reason)
        } else {
            setReason(
                user.data
                    ? 'Requested from the web UI by ' + user.data.profile.preferred_username
                    : '-'
            )
        }
    }, [props.change, props.changeRef, props.project, props.jobName, props.reason, user.data])

    function handleConfirm() {
        let ah_change = change === '' ? null : change
        let ah_ref = changeRef === '' ? null : changeRef

        autohold(tenant.apiPrefix, project, job_name, ah_change, ah_ref, reason, parseInt(count), parseInt(nodeHoldExpiration))
            .then(() => {
                /* TODO it looks like there is a delay in the registering of the autohold request
                   by the backend, meaning we sometimes do not get the newly created request after
                   the dispatch. A solution could be to  make the autoholds page auto-refreshing
                   like the status page.*/
                dispatch(fetchAutoholds(tenant))
                dispatch(addNotification(
                    {
                        text: 'Autohold request set successfully.',
                        type: 'success',
                        status: '',
                        url: '',
                    }))
            })
            .catch(error => {
                dispatch(addAutoholdError(error))
            })
        setShowAutoholdModal(false)
    }

    return (
        <Modal
            variant={ModalVariant.small}
            isOpen={showAutoholdModal}
            title='Create an Autohold Request'
            onClose={() => { setShowAutoholdModal(false) }}
            actions={[
                <Button
                    key="autohold_confirm"
                    variant="primary"
                    onClick={() => handleConfirm()}>Create</Button>,
                <Button
                    key="autohold_cancel"
                    variant="link"
                    onClick={() => { setShowAutoholdModal(false) }}>Cancel</Button>
            ]}>
            <Form isHorizontal>
                <FormGroup
                    label="Project"
                    isRequired
                    fieldId="ah-form-project"
                    helperText="The project for which to hold the next failing build">
                    <TextInput
                        value={project}
                        isRequired
                        type="text"
                        id="ah-form-ref"
                        name="project"
                        onChange={(value) => { setProject(value) }} />
                </FormGroup>
                <FormGroup
                    label="Job"
                    isRequired
                    fieldId="ah-form-job-name"
                    helperText="The job for which to hold the next failing build">
                    <TextInput
                        value={job_name}
                        isRequired
                        type="text"
                        id="ah-form-job-name"
                        name="job_name"
                        onChange={(value) => { setJob_name(value) }} />
                </FormGroup>
                <FormGroup
                    label="Change"
                    fieldId="ah-form-change"
                    helperText="The change for which to hold the next failing build">
                    <TextInput
                        value={change}
                        type="text"
                        id="ah-form-change"
                        name="change"
                        onChange={(value) => { setChange(value) }} />
                </FormGroup>
                <FormGroup
                    label="Ref"
                    fieldId="ah-form-ref"
                    helperText="The ref for which to hold the next failing build">
                    <TextInput
                        value={changeRef}
                        type="text"
                        id="ah-form-ref"
                        name="change"
                        onChange={(value) => { setChangeRef(value) }} />
                </FormGroup>
                <FormGroup
                    label="Reason"
                    isRequired
                    fieldId="ah-form-reason"
                    helperText="A descriptive reason for holding the next failing build">
                    <TextInput
                        value={reason}
                        isRequired
                        type="text"
                        id="ah-form-reason"
                        name="reason"
                        onChange={(value) => { setReason(value) }} />
                </FormGroup>
                <FormGroup
                    label="Count"
                    isRequired
                    fieldId="ah-form-count"
                    helperText="How many times a failing build should be held">
                    <TextInput
                        value={count}
                        isRequired
                        type="number"
                        id="ah-form-count"
                        name="count"
                        onChange={(value) => { setCount(value) }} />
                </FormGroup>
                <FormGroup
                    label="Node Hold Expires in (s)"
                    isRequired
                    fieldId="ah-form-nhe"
                    helperText="How long nodes should be kept in HELD state (seconds)">
                    <TextInput
                        value={nodeHoldExpiration}
                        isRequired
                        type="number"
                        id="ah-form-count"
                        name="nodeHoldExpiration"
                        onChange={(value) => { setNodeHoldExpiration(value) }} />
                </FormGroup>
            </Form>
        </Modal>
    )
}

AutoholdModal.propTypes = {
    tenant: PropTypes.object,
    user: PropTypes.object,
    change: PropTypes.string,
    changeRef: PropTypes.string,
    project: PropTypes.string,
    jobName: PropTypes.string,
    reason: PropTypes.string,
    showAutoholdModal: PropTypes.bool,
    setShowAutoholdModal: PropTypes.func,
}

export default connect((state) => ({
    tenant: state.tenant,
    user: state.user,
}))(AutoholdModal)
