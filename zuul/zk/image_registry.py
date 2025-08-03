# Copyright 2024 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections

from zuul.zk.launcher import LockableZKObjectCache
from zuul.model import ImageBuildArtifact, ImageUpload


class ImageBuildRegistry(LockableZKObjectCache):

    def __init__(self, zk_client, updated_event=None):
        self.builds_by_image_name = collections.defaultdict(set)
        super().__init__(
            zk_client,
            updated_event,
            root=ImageBuildArtifact.ROOT,
            items_path=ImageBuildArtifact.IMAGES_PATH,
            locks_path=ImageBuildArtifact.LOCKS_PATH,
            zkobject_class=ImageBuildArtifact,
        )

    def postCacheHook(self, event, data, stat, key, obj):
        exists = key in self._cached_objects
        if exists:
            if obj:
                builds = self.builds_by_image_name[obj.canonical_name]
                builds.add(key)
        else:
            if obj:
                builds = self.builds_by_image_name[obj.canonical_name]
                builds.discard(key)
        super().postCacheHook(event, data, stat, key, obj)

    def getArtifactsForImage(self, image_canonical_name):
        keys = list(self.builds_by_image_name[image_canonical_name])
        arts = [self._cached_objects.get(key) for key in keys]
        arts = [a for a in arts if a is not None]
        # Sort in a stable order, primarily by timestamp, then format
        # for identical timestamps.
        arts = sorted(arts, key=lambda x: x.format)
        arts = sorted(arts, key=lambda x: x.timestamp)
        return arts

    def getAllArtifacts(self):
        keys = []
        for image_canonical_name in self.builds_by_image_name.keys():
            keys.extend(self.builds_by_image_name[image_canonical_name])
        arts = [self._cached_objects.get(key) for key in keys]
        arts = [a for a in arts if a is not None]
        # Sort in a stable order, primarily by timestamp, then format
        # for identical timestamps.
        arts = sorted(arts, key=lambda x: x.format)
        arts = sorted(arts, key=lambda x: x.timestamp)
        return arts


class ImageUploadRegistry(LockableZKObjectCache):

    def __init__(self, zk_client, updated_event=None):
        self.uploads_by_image_name = collections.defaultdict(set)
        super().__init__(
            zk_client,
            updated_event,
            root=ImageUpload.ROOT,
            items_path=ImageUpload.UPLOADS_PATH,
            locks_path=ImageUpload.LOCKS_PATH,
            zkobject_class=ImageUpload,
        )

    def postCacheHook(self, event, data, stat, key, obj):
        exists = key in self._cached_objects
        if exists:
            if obj:
                uploads = self.uploads_by_image_name[obj.canonical_name]
                uploads.add(key)
        else:
            if obj:
                uploads = self.uploads_by_image_name[obj.canonical_name]
                uploads.discard(key)
        super().postCacheHook(event, data, stat, key, obj)

    def getUploadsForImage(self, image_canonical_name):
        keys = list(self.uploads_by_image_name[image_canonical_name])
        uploads = [self._cached_objects.get(key) for key in keys]
        uploads = [u for u in uploads if u is not None]
        uploads = sorted(uploads, key=lambda x: x.timestamp)
        return uploads
