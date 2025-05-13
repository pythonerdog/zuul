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
import base64
import types

from zuul.lib import encryption

import yaml
from yaml import YAMLError  # noqa: F401


try:
    # Explicit type ignore to deal with provisional import failure
    # Details at https://github.com/python/mypy/issues/1153
    from yaml import cyaml
    import _yaml
    SafeLoader = cyaml.CSafeLoader
    SafeDumper = cyaml.CSafeDumper
    Mark = _yaml.Mark
except ImportError:
    SafeLoader = yaml.SafeLoader
    SafeDumper = yaml.SafeDumper
    Mark = yaml.Mark


class OverrideValue:
    def __init__(self, value, override):
        self.value = value
        self.override = override


# Generally it only makes sense to override lists or dicts, but
# because of the to_list construction, we might end up with strings
# too.
class OverrideStr(OverrideValue):
    pass


class OverrideList(OverrideValue):
    pass


class OverrideDict(OverrideValue):
    pass


class Override:
    yaml_tag = u'!override'
    override_value = True

    @classmethod
    def from_yaml(cls, loader, node):
        if isinstance(node, yaml.MappingNode):
            return OverrideDict(loader.construct_mapping(node),
                                cls.override_value)
        elif isinstance(node, yaml.SequenceNode):
            return OverrideList(loader.construct_sequence(node),
                                cls.override_value)
        elif isinstance(node, yaml.ScalarNode):
            tag = loader.resolve(yaml.ScalarNode, node.value, (True, False))
            node = yaml.ScalarNode(tag, node.value,
                                   node.start_mark, node.end_mark)
            raw_value = loader.construct_object(node)
            if isinstance(raw_value, str):
                return OverrideStr(raw_value, cls.override_value)
            raise Exception("Unsupported type for scalar override control: "
                            f"{type(raw_value)}")
        raise Exception(f"Unsupported type for override control: {type(node)}")


class Inherit(Override):
    yaml_tag = u'!inherit'
    override_value = False


class EncryptedPKCS1_OAEP:
    yaml_tag = u'!encrypted/pkcs1-oaep'

    def __init__(self, ciphertext):
        if isinstance(ciphertext, list):
            self.ciphertext = [base64.b64decode(x.value)
                               for x in ciphertext]
        else:
            self.ciphertext = base64.b64decode(ciphertext)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if not isinstance(other, EncryptedPKCS1_OAEP):
            return False
        return (self.ciphertext == other.ciphertext)

    @classmethod
    def from_yaml(cls, loader, node):
        return cls(node.value)

    @classmethod
    def to_yaml(cls, dumper, data):
        ciphertext = data.ciphertext
        if isinstance(ciphertext, list):
            ciphertext = [yaml.ScalarNode(tag='tag:yaml.org,2002:str',
                                          value=base64.b64encode(x))
                          for x in ciphertext]
            return yaml.SequenceNode(tag=cls.yaml_tag,
                                     value=ciphertext)
        ciphertext = base64.b64encode(ciphertext).decode('utf8')
        return yaml.ScalarNode(tag=cls.yaml_tag, value=ciphertext)

    def decrypt(self, private_key):
        if isinstance(self.ciphertext, list):
            return ''.join([
                encryption.decrypt_pkcs1_oaep(chunk, private_key).
                decode('utf8')
                for chunk in self.ciphertext])
        else:
            return encryption.decrypt_pkcs1_oaep(self.ciphertext,
                                                 private_key).decode('utf8')


class ZuulConfigKey(str):
    def __new__(cls, s, line):
        self = super().__new__(cls, s)
        self.line = line
        return self

    def __copy__(self):
        return ZuulConfigKey(self, self.line)

    def __deepcopy__(self, memo):
        return self.__copy__()

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.representer.SafeRepresenter.represent_str(
            dumper, str(data))


def safe_load(stream, *args, **kwargs):
    return yaml.load(stream, *args, Loader=SafeLoader, **kwargs)


def safe_dump(stream, *args, **kwargs):
    return yaml.dump(stream, *args, Dumper=SafeDumper, **kwargs)


class EncryptedDumper(SafeDumper):
    pass


class EncryptedLoader(SafeLoader):
    pass


# Add support for encrypted objects
EncryptedDumper.add_representer(EncryptedPKCS1_OAEP,
                                EncryptedPKCS1_OAEP.to_yaml)
EncryptedLoader.add_constructor(EncryptedPKCS1_OAEP.yaml_tag,
                                EncryptedPKCS1_OAEP.from_yaml)
# Also add support for serializing frozen data
EncryptedDumper.add_representer(
    types.MappingProxyType,
    yaml.representer.SafeRepresenter.represent_dict)
EncryptedDumper.add_representer(
    ZuulConfigKey,
    ZuulConfigKey.to_yaml)
# Add support for override control
EncryptedLoader.add_constructor(Override.yaml_tag,
                                Override.from_yaml)
EncryptedLoader.add_constructor(Inherit.yaml_tag,
                                Inherit.from_yaml)


def encrypted_dump(data, *args, **kwargs):
    return yaml.dump(data, *args, Dumper=EncryptedDumper, **kwargs)


def encrypted_load(stream, *args, **kwargs):
    return yaml.load(stream, *args, Loader=EncryptedLoader, **kwargs)


# Add support for the Ansible !unsafe tag
# Note that "unsafe" here is used differently than "safe" from PyYAML

class AnsibleUnsafeStr:
    yaml_tag = u'!unsafe'

    def __init__(self, value):
        self.value = value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if isinstance(other, AnsibleUnsafeStr):
            return self.value == other.value
        return self.value == other

    @classmethod
    def from_yaml(cls, loader, node):
        return cls(node.value)

    @classmethod
    def to_yaml(cls, dumper, data):
        return yaml.ScalarNode(tag=cls.yaml_tag, value=data.value)


class AnsibleUnsafeDumper(SafeDumper):
    pass


class AnsibleUnsafeDumperWithoutAliases(SafeDumper):
    def ignore_aliases(self, data):
        return True


class AnsibleUnsafeLoader(SafeLoader):
    pass


AnsibleUnsafeDumper.add_representer(AnsibleUnsafeStr,
                                    AnsibleUnsafeStr.to_yaml)
AnsibleUnsafeLoader.add_constructor(AnsibleUnsafeStr.yaml_tag,
                                    AnsibleUnsafeStr.from_yaml)


def ansible_unsafe_dump(data, *args, **kwargs):
    ignore_aliases = kwargs.pop('ignore_aliases', False)
    if ignore_aliases:
        return yaml.dump(data, *args, Dumper=AnsibleUnsafeDumperWithoutAliases,
                         **kwargs)
    else:
        return yaml.dump(data, *args, Dumper=AnsibleUnsafeDumper, **kwargs)


def ansible_unsafe_load(stream, *args, **kwargs):
    return yaml.load(stream, *args, Loader=AnsibleUnsafeLoader, **kwargs)


def mark_strings_unsafe(d):
    """Traverse a json-style data structure and replace every string value
    with an AnsibleUnsafeStr

    Returns the new structure.
    """
    if isinstance(d, tuple):
        d = list(d)

    if isinstance(d, dict):
        newdict = {}
        for key, value in d.items():
            newdict[key] = mark_strings_unsafe(value)
        return newdict
    elif isinstance(d, list):
        return [mark_strings_unsafe(v) for v in d]
    elif isinstance(d, int):
        return d
    elif isinstance(d, float):
        return d
    elif isinstance(d, type(None)):
        return d
    elif isinstance(d, bool):
        return d
    elif isinstance(d, AnsibleUnsafeStr):
        return d
    elif isinstance(d, str):
        return AnsibleUnsafeStr(d)
    else:
        raise Exception("Unhandled type: %s", type(d))
