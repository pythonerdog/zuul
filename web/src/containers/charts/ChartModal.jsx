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

import * as React from 'react'
import PropTypes from 'prop-types'

import { Button, Modal } from '@patternfly/react-core'


function ChartModal(props) {
    const { chart, isOpen, title, onClose } = props

    return (
        <Modal
            isOpen={isOpen}
            width={'75%'}
            title={title ? title : 'No title'}
            onClose={onClose}
            actions={[
                <Button key='chart-modal-close' variant="primary" onClick={onClose}>Close</Button>,
            ]}>
            <center>
                {chart}
            </center>
        </Modal>
    )
}

ChartModal.propTypes = {
    chart: PropTypes.object.isRequired,
    isOpen: PropTypes.bool,
    title: PropTypes.string,
    onClose: PropTypes.func.isRequired,
}

export { ChartModal }