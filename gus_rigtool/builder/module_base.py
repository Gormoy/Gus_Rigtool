"""The base of every builder module (kept apart so chain.py can use it without a circular import)."""

import copy


LIMB_ORIENT = {"aim": "X", "up": "Y", "up_mode": "plane", "world_up": [0, 1, 0], "behavior_right": True}
SPINE_ORIENT = {"aim": "X", "up": "Z", "up_mode": "world", "world_up": [0, 0, 1], "behavior_right": True}
FINGER_ORIENT = {"aim": "X", "up": "Y", "up_mode": "world", "world_up": [0, 1, 0], "behavior_right": True}


class Module(object):
    TYPE = ""
    LABEL = ""
    SIDES = ("C",)
    ATTACH = ""                       # default "module:part" this module hangs from
    CONTROLS = {}                     # kind: [shape, size as a fraction of the height]
    ORIENT = SPINE_ORIENT
    OPTIONS = {}                      # option: default
    OPTION_LABELS = {}                # option: (label, kind, choices)
    OPTION_GROUPS = []                # [(group title, [option keys])] for the settings form
    OPTION_NEEDS = {}                 # field path: (path it depends on, test): greyed out when the test fails
    DESCRIPTION = ""                  # what it builds (the '?' of its settings)

    def default_settings(self, side="C"):
        return {
            "names": copy.deepcopy(self.default_names()),
            "attach": self.ATTACH,
            "controls": copy.deepcopy(self.CONTROLS),
            "orient": copy.deepcopy(self.ORIENT),
            "options": copy.deepcopy(self.OPTIONS),
            "guide_size": 1.0,
        }

    def default_names(self):
        return {}

    SIZED = []                        # [(names list, option with its count, pattern for new names)]

    def complete(self, settings):
        """Fill in anything missing (settings saved by an older version), and size the name lists
        that follow a count option (a new name is made for each one more: spine_05, finger6...)."""
        had = set((settings.get("options") or {}).keys())
        base = self.default_settings()
        for key, value in base.items():
            if key not in settings:
                settings[key] = value
            elif isinstance(value, dict):
                for k, v in value.items():
                    settings[key].setdefault(k, v)
        for list_key, count_key, pattern in self.SIZED:
            lst = list(settings["names"].get(list_key) or [])
            if count_key not in had:                    # older settings: the list decides
                settings["options"][count_key] = max(1, len(lst))
            count = max(1, int(settings["options"].get(count_key) or 1))
            i = len(lst)
            while len(lst) < count:
                i += 1
                name = pattern % i
                if name not in lst:
                    lst.append(name)
            settings["names"][list_key] = lst[:count]
        return settings

    def guide_specs(self, settings, height, side):
        """[{'role', 'part', 'pos', 'parent', 'kind'}] (left-side positions; right is mirrored)."""
        raise NotImplementedError

    def preview_names(self, settings, side):
        """The main names this module will make (for the preview list)."""
        return []

    def build(self, ctx):
        raise NotImplementedError


def _mirror_specs(specs, side):
    if side == "R":
        for s in specs:
            s["pos"] = [-s["pos"][0], s["pos"][1], s["pos"][2]]
    return specs


def _chain_roles(prefix, count):
    return ["%s%d" % (prefix, i) for i in range(count)]


