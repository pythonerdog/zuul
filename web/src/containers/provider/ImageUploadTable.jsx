// Copyright 2020 Red Hat, Inc
// Copyright 2022, 2024 Acme Gating, LLC
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

import React, { useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import PropTypes from 'prop-types'
import {
  Button,
  EmptyState,
  EmptyStateBody,
  Spinner,
  Title,
  Modal,
  ModalVariant,
} from '@patternfly/react-core'
import {
  Table,
  TableHeader,
  TableBody,
  TableVariant,
} from '@patternfly/react-table'
import { fetchImages } from '../../actions/images'
import { fetchProviders } from '../../actions/providers'
import { addNotification, addApiError } from '../../actions/notifications'
import { deleteImageUpload } from '../../api'

function ImageUploadTable(props) {
  const { build, uploads, fetching } = props
  const [showDeleteUploadModal, setShowDeleteUploadModal] = useState(false)
  const [pendingDeleteRow, setPendingDeleteRow] = useState(null)
  const tenant = useSelector((state) => state.tenant)
  const user = useSelector((state) => state.user)
  const dispatch = useDispatch()

  const columns = [
    {
      title: 'UUID',
      dataLabel: 'UUID',
    },
    {
      title: 'Timestamp',
      dataLabel: 'Timestamp',
    },
    {
      title: 'Validated',
      dataLabel: 'Validated',
    },
    {
      title: 'Endpoint',
      dataLabel: 'Endpoint',
    },
    {
      title: 'External ID',
      dataLabel: 'External ID',
    },
  ]

  function createImageUploadRow(upload) {
    return {
      _uuid: upload.uuid,
      canDelete: build.build_tenant,
      cells: [
        {
          title: upload.uuid
        },
        {
          title: upload.timestamp
        },
        {
          title: upload.validated.toString()
        },
        {
          title: upload.endpoint_name
        },
        {
          title: upload.external_id
        },
      ]
    }
  }

  function createFetchingRow() {
    const rows = [
      {
        heightAuto: true,
        cells: [
          {
            props: { colSpan: 8 },
            title: (
              <center>
                <Spinner size="xl" />
              </center>
            ),
          },
        ],
      },
    ]
    return rows
  }

  const actionResolver = (rowData) => {
    if (rowData.canDelete &&
        user.isAdmin &&
        user.scope.indexOf(tenant.name) !== -1) {
      return [
        {
          title: 'Delete upload',
          onClick: () => {
            setPendingDeleteRow(rowData)
            setShowDeleteUploadModal(true)
          }
        },
      ]
    }
    return []
  }

  function renderDeleteUploadModal() {
    const title = 'Delete image upload'
    return (
      <Modal
        variant={ModalVariant.small}
        isOpen={showDeleteUploadModal}
        title={title}
        onClose={() => { setShowDeleteUploadModal(false) }}
        actions={[
          <Button key="confirm" variant="primary"
                  onClick={() => {
                    setShowDeleteUploadModal(false)
                    deleteImageUpload(tenant.apiPrefix,
                                      pendingDeleteRow._uuid
                                     ).then(() => {
                      dispatch(addNotification(
                        {
                          text: 'Delete successful.',
                          type: 'success',
                          status: '',
                          url: '',
                        }))
                      dispatch(fetchProviders(tenant))
                      dispatch(fetchImages(tenant))
                    })
                      .catch(error => {
                        dispatch(addApiError(error))
                      })
                  }}>
            Confirm
          </Button>,
          <Button key="cancel" variant="link"
                  onClick={() => {setShowDeleteUploadModal(false) }}>
            Cancel
          </Button>,
        ]}>
        <p>
          Please confirm that you want to delete this image upload.
        </p>
      </Modal>
    )
  }

  const haveUploads = uploads && uploads.length > 0

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    columns[0].dataLabel = ''
  } else {
    if (haveUploads) {
      rows = uploads.map((upload) => createImageUploadRow(upload))
    }
  }

  return (
    <>
      <Title headingLevel="h3">
        Image Uploads
      </Title>
      <Table
        aria-label="Image Upload Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        actionResolver={actionResolver}
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any build artifacts but are also not
          fetching */}
      {!fetching && !haveUploads && (
        <EmptyState>
          <Title headingLevel="h1">No image uploads found</Title>
          <EmptyStateBody>
            Nothing to display.
          </EmptyStateBody>
        </EmptyState>
      )}
      {renderDeleteUploadModal()}
    </>
  )
}

ImageUploadTable.propTypes = {
  build: PropTypes.object,
  uploads: PropTypes.array,
  fetching: PropTypes.bool.isRequired,
}

export default ImageUploadTable
