# Copyright 2016 Red Hat, Inc.
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

import abc


class BaseExecutionContext(object, metaclass=abc.ABCMeta):
    """The execution interface returned by a wrapper.

    Wrapper drivers return instances which implement this interface.

    It is used to hold information and aid in the execution of a
    single command.

    """

    @abc.abstractmethod
    def getPopen(self, **kwargs):
        """Create and return a subprocess.Popen factory wrapped however the
        driver sees fit.

        This method is required by the interface

        :arg dict kwargs: key/values for use by driver as needed

        :returns: a callable that takes the same args as subprocess.Popen
        :rtype: Callable
        """
        pass

    @abc.abstractmethod
    def getNamespacePids(self, proc):
        """Given a Popen object, return the namespace and a list of host-side
        process ids in proc's first child namespace.

        :arg Popen proc: The Popen object that is the parent of the namespace.

        :returns: A tuple of the namespace id and all of the process
            ids in the namespace.  The namespace id is None if no namespace
            was found.
        :rtype: tuple(int, list[int])

        """
        pass
