from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import namedtuple
import logging
import json
# For compatibility under py2 to consider unicode as str
from six import string_types

from numbers import Number

from ray.tune import TuneError

logger = logging.getLogger(__name__)


class Resources(
        namedtuple("Resources", [
            "cpu", "gpu", "extra_cpu", "extra_gpu", "custom_resources",
            "extra_custom_resources"
        ])):
    """Ray resources required to schedule a trial.

    Attributes:
        cpu (float): Number of CPUs to allocate to the trial.
        gpu (float): Number of GPUs to allocate to the trial.
        extra_cpu (float): Extra CPUs to reserve in case the trial needs to
            launch additional Ray actors that use CPUs.
        extra_gpu (float): Extra GPUs to reserve in case the trial needs to
            launch additional Ray actors that use GPUs.
        custom_resources (dict): Mapping of resource to quantity to allocate
            to the trial.
        extra_custom_resources (dict): Extra custom resources to reserve in
            case the trial needs to launch additional Ray actors that use
            any of these custom resources.

    """

    __slots__ = ()

    def __new__(cls,
                cpu,
                gpu,
                extra_cpu=0,
                extra_gpu=0,
                custom_resources=None,
                extra_custom_resources=None):
        custom_resources = custom_resources or {}
        extra_custom_resources = extra_custom_resources or {}
        leftovers = set(custom_resources) ^ set(extra_custom_resources)

        for value in leftovers:
            custom_resources.setdefault(value, 0)
            extra_custom_resources.setdefault(value, 0)

        all_values = [cpu, gpu, extra_cpu, extra_gpu]
        all_values += list(custom_resources.values())
        all_values += list(extra_custom_resources.values())
        assert len(custom_resources) == len(extra_custom_resources)
        for entry in all_values:
            assert isinstance(entry, Number), "Improper resource value."
        return super(Resources,
                     cls).__new__(cls, cpu, gpu, extra_cpu, extra_gpu,
                                  custom_resources, extra_custom_resources)

    def summary_string(self):
        summary = "{} CPUs, {} GPUs".format(self.cpu + self.extra_cpu,
                                            self.gpu + self.extra_gpu)
        custom_summary = ", ".join([
            "{} {}".format(self.get_res_total(res), res)
            for res in self.custom_resources
        ])
        if custom_summary:
            summary += " ({})".format(custom_summary)
        return summary

    def cpu_total(self):
        return self.cpu + self.extra_cpu

    def gpu_total(self):
        return self.gpu + self.extra_gpu

    def get_res_total(self, key):
        return self.custom_resources.get(
            key, 0) + self.extra_custom_resources.get(key, 0)

    def get(self, key):
        return self.custom_resources.get(key, 0)

    def is_nonnegative(self):
        all_values = [self.cpu, self.gpu, self.extra_cpu, self.extra_gpu]
        all_values += list(self.custom_resources.values())
        all_values += list(self.extra_custom_resources.values())
        return all(v >= 0 for v in all_values)

    @classmethod
    def subtract(cls, original, to_remove):
        cpu = original.cpu - to_remove.cpu
        gpu = original.gpu - to_remove.gpu
        extra_cpu = original.extra_cpu - to_remove.extra_cpu
        extra_gpu = original.extra_gpu - to_remove.extra_gpu
        all_resources = set(original.custom_resources).union(
            set(to_remove.custom_resources))
        new_custom_res = {
            k: original.custom_resources.get(k, 0) -
            to_remove.custom_resources.get(k, 0)
            for k in all_resources
        }
        extra_custom_res = {
            k: original.extra_custom_resources.get(k, 0) -
            to_remove.extra_custom_resources.get(k, 0)
            for k in all_resources
        }
        return Resources(cpu, gpu, extra_cpu, extra_gpu, new_custom_res,
                         extra_custom_res)

    def to_json(self):
        return resources_to_json(self)


def json_to_resources(data):
    if data is None or data == "null":
        return None
    if isinstance(data, string_types):
        data = json.loads(data)
    for k in data:
        if k in ["driver_cpu_limit", "driver_gpu_limit"]:
            raise TuneError(
                "The field `{}` is no longer supported. Use `extra_cpu` "
                "or `extra_gpu` instead.".format(k))
        if k not in Resources._fields:
            raise ValueError(
                "Unknown resource field {}, must be one of {}".format(
                    k, Resources._fields))
    return Resources(
        data.get("cpu", 1), data.get("gpu", 0), data.get("extra_cpu", 0),
        data.get("extra_gpu", 0), data.get("custom_resources"),
        data.get("extra_custom_resources"))


def resources_to_json(resources):
    if resources is None:
        return None
    return {
        "cpu": resources.cpu,
        "gpu": resources.gpu,
        "extra_cpu": resources.extra_cpu,
        "extra_gpu": resources.extra_gpu,
        "custom_resources": resources.custom_resources.copy(),
        "extra_custom_resources": resources.extra_custom_resources.copy()
    }
