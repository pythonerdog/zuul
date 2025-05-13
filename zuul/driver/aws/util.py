# Copyright 2018 Red Hat
# Copyright 2022-2024 Acme Gating, LLC
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


def tag_dict_to_list(tagdict):
    return [{"Key": k, "Value": v} for k, v in tagdict.items()]


def tag_list_to_dict(taglist):
    if taglist is None:
        return {}
    return {t["Key"]: t["Value"] for t in taglist}
