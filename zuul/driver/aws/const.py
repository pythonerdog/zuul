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

import itertools

# This is a map of instance types to quota codes.  There does not
# appear to be an automated way to determine what quota code to use
# for an instance type, therefore this list was manually created by
# visiting
# https://us-west-1.console.aws.amazon.com/servicequotas/home/services/ec2/quotas
# and filtering by "Instances".  An example description is "Running
# On-Demand P instances" which we can infer means we should use that
# quota code for instance types starting with the letter "p".  All
# instance type names follow the format "([a-z\-]+)\d", so we can
# match the first letters (up to the first number) of the instance
# type name with the letters in the quota name.  The prefix "u-" for
# "Running On-Demand High Memory instances" was determined from
# https://aws.amazon.com/ec2/instance-types/high-memory/


ON_DEMAND = 0
SPOT = 1

INSTANCE_QUOTA_CODES = {
    # INSTANCE FAMILY: [ON-DEMAND, SPOT]
    'a': ['L-1216C47A', 'L-34B43A08'],
    'c': ['L-1216C47A', 'L-34B43A08'],
    'd': ['L-1216C47A', 'L-34B43A08'],
    'h': ['L-1216C47A', 'L-34B43A08'],
    'i': ['L-1216C47A', 'L-34B43A08'],
    'm': ['L-1216C47A', 'L-34B43A08'],
    'r': ['L-1216C47A', 'L-34B43A08'],
    't': ['L-1216C47A', 'L-34B43A08'],
    'z': ['L-1216C47A', 'L-34B43A08'],
    'dl': ['L-6E869C2A', 'L-85EED4F7'],
    'f': ['L-74FC7D96', 'L-88CF9481'],
    'g': ['L-DB2E81BA', 'L-3819A6DF'],
    'vt': ['L-DB2E81BA', 'L-3819A6DF'],
    'u-': ['L-43DA4232', ''],          # 'high memory'
    'inf': ['L-1945791B', 'L-B5D1601B'],
    'p': ['L-417A185B', 'L-7212CCBC'],
    'x': ['L-7295265B', 'L-E3A00192'],
    'trn': ['L-2C3B7624', 'L-6B0D517C'],
    'hpc': ['L-F7808C92', '']
}

HOST_QUOTA_CODES = {
    'a1': 'L-949445B0',
    'c3': 'L-8D142A2E',
    'c4': 'L-E4BF28E0',
    'c5': 'L-81657574',
    'c5a': 'L-03F01FD8',
    'c5d': 'L-C93F66A2',
    'c5n': 'L-20F13EBD',
    'c6a': 'L-D75D2E84',
    'c6g': 'L-A749B537',
    'c6gd': 'L-545AED39',
    'c6gn': 'L-5E3A299D',
    'c6i': 'L-5FA3355A',
    'c6id': 'L-1BBC5241',
    'c6in': 'L-6C2C40CC',
    'c7a': 'L-698B67E5',
    'c7g': 'L-13B8FCE8',
    'c7gd': 'L-EF58B059',
    'c7gn': 'L-97677CE3',
    'c7i': 'L-587AA6E3',
    'd2': 'L-8B27377A',
    'dl1': 'L-AD667A3D',
    'f1': 'L-5C4CD236',
    'g3': 'L-DE82EABA',
    'g3s': 'L-9675FDCD',
    'g4ad': 'L-FD8E9B9A',
    'g4dn': 'L-CAE24619',
    'g5': 'L-A6E7FE5E',
    'g5g': 'L-4714FFEA',
    'g6': 'L-B88B9D6B',
    'gr6': 'L-E68C3AFF',
    'h1': 'L-84391ECC',
    'i2': 'L-6222C1B6',
    'i3': 'L-8E60B0B1',
    'i3en': 'L-77EE2B11',
    'i4g': 'L-F62CBADB',
    'i4i': 'L-0300530D',
    'im4gn': 'L-93155D6F',
    'inf': 'L-5480EFD2',
    'inf2': 'L-E5BCF7B5',
    'is4gen': 'L-CB4F5825',
    'm3': 'L-3C82F907',
    'm4': 'L-EF30B25E',
    'm5': 'L-8B7BF662',
    'm5a': 'L-B10F70D6',
    'm5ad': 'L-74F41837',
    'm5d': 'L-8CCBD91B',
    'm5dn': 'L-DA07429F',
    'm5n': 'L-24D7D4AD',
    'm5zn': 'L-BD9BD803',
    'm6a': 'L-80F2B67F',
    'm6g': 'L-D50A37FA',
    'm6gd': 'L-84FB37AA',
    'm6i': 'L-D269BEFD',
    'm6id': 'L-FDB0A352',
    'm6idn': 'L-9721EDD9',
    'm6in': 'L-D037CF10',
    'm7a': 'L-4740F819',
    'm7g': 'L-9126620E',
    'm7gd': 'L-F8516154',
    'm7i': 'L-30E31217',
    'mac1': 'L-A8448DC5',
    'mac2': 'L-5D8DADF5',
    'mac2-m2': 'L-B90B5B66',
    'mac2-m2pro': 'L-14F120D1',
    'p2': 'L-2753CF59',
    'p3': 'L-A0A19F79',
    'p3dn': 'L-B601B3B6',
    'p4d': 'L-86A789C3',
    'p5': 'L-5136197D',
    'r3': 'L-B7208018',
    'r4': 'L-313524BA',
    'r5': 'L-EA4FD6CF',
    'r5a': 'L-8FE30D52',
    'r5ad': 'L-EC7178B6',
    'r5b': 'L-A2D59C67',
    'r5d': 'L-8814B54F',
    'r5dn': 'L-4AB14223',
    'r5n': 'L-52EF324A',
    'r6a': 'L-BC1589C5',
    'r6g': 'L-B6D6065D',
    'r6gd': 'L-EF284EFB',
    'r6i': 'L-F13A970A',
    'r6id': 'L-B89271A9',
    'r6idn': 'L-C4EABC2C',
    'r6in': 'L-EA99608B',
    'r7a': 'L-4D15192B',
    'r7g': 'L-67B8B4C7',
    'r7gd': 'L-01137DCE',
    'r7i': 'L-55E05032',
    'r7iz': 'L-BC9FCC71',
    't3': 'L-1586174D',
    'trn1': 'L-5E4FB836',
    'trn1n': 'L-39926A58',
    'u-12tb1': 'L-D6994875',
    'u-18tb1': 'L-5F7FD336',
    'u-24tb1': 'L-FACBE655',
    'u-3tb1': 'L-7F5506AB',
    'u-6tb1': 'L-89870E8E',
    'u-9tb1': 'L-98E1FFAC',
    'u7in-16tb': 'L-75B9BECB',
    'u7in-24tb': 'L-CA51381E',
    'u7in-32tb': 'L-9D28191F',
    'vt1': 'L-A68CFBF7',
    'x1': 'L-DE3D9563',
    'x1e': 'L-DEF8E115',
    'x2gd': 'L-5CC9EA82',
    'x2idn': 'L-A84ABF80',
    'x2iedn': 'L-D0AA08B1',
    'x2iezn': 'L-888B4496',
    'z1d': 'L-F035E935',
}

VOLUME_QUOTA_CODES = {
    'io1': dict(iops='L-B3A130E6', storage='L-FD252861'),
    'io2': dict(iops='L-8D977E7E', storage='L-09BD8365'),
    'sc1': dict(storage='L-17AF77E8'),
    'gp2': dict(storage='L-D18FCD1D'),
    'gp3': dict(storage='L-7A658B76'),
    'standard': dict(storage='L-9CF3C2EB'),
    'st1': dict(storage='L-82ACEF56'),
}

ALL_QUOTA_CODES = set(itertools.chain(
    (x for x in itertools.chain.from_iterable(
        INSTANCE_QUOTA_CODES.values()) if x),
    HOST_QUOTA_CODES.values(),
    itertools.chain.from_iterable(
        (x.values() for x in VOLUME_QUOTA_CODES.values())
    ),
))
