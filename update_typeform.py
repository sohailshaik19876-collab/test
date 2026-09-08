#!/usr/bin/env python3
"""
update_typeform.py

Loads a Typeform backup (typeform_backup_qd0zpSvg.json), inserts a set of new
sections/fields together with the conditional logic that connects them, and
writes typeform_backup_qd0zpSvg_UPDATED.json.

Guarantees:
  * All existing fields are preserved unchanged (ids, refs, titles, order).
  * All existing logic is preserved; exactly one existing rule is retargeted
    (the mortgage purchase-info group) so its jump flows into the first new
    field instead of skipping past everything that is being inserted.
  * theme, settings, hidden fields, screens and metadata are untouched.

Inserted sections:
  * Mortgage Costs (£)              -> after the mortgage purchase/remortgage
                                       groups, before Section 10 Sick Pay Info
  * Additional Property             -> before Section 10 (conditional)
  * Future Changes                  -> before Section 10 (conditional)
  * Sale of Existing Property       -> before Section 10 (conditional)
  * Monthly Budget                  -> before Section 10 (always shown)
  * General Insurance               -> immediately before Additional Services
"""

import json
import secrets
import string
import uuid

INPUT_FILE = "typeform_backup_qd0zpSvg.json"
OUTPUT_FILE = "typeform_backup_qd0zpSvg_UPDATED.json"

# Anchor refs in the source form (with title fallbacks used if a ref is absent).
SECTION_10_REF = "9a07724b-0314-46f6-9373-fcc42584c84a"      # Section 10: Sick Pay Info
SECTION_10_TITLE = "Section 10: Sick Pay Info"
ADDITIONAL_SERVICES_REF = "544ccd7a-813a-4dd4-8c51-1429461c6967"  # Section 12
ADDITIONAL_SERVICES_TITLE = "Section 12: Additional Services"
PURCHASE_GROUP_REF = "e79a4030-f566-495c-970b-8e38cee1d04d"  # mortgage purchase group


# --------------------------------------------------------------------------- #
# Unique id / ref generation
# --------------------------------------------------------------------------- #
_ALPHABET = string.ascii_letters + string.digits


def _collect(obj, key, acc):
    """Recursively gather every value stored under `key` (ids or refs)."""
    if isinstance(obj, dict):
        val = obj.get(key)
        if isinstance(val, str):
            acc.add(val)
        for v in obj.values():
            _collect(v, key, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, key, acc)


class IdFactory:
    """Hands out ids/refs that never collide with anything already in the form."""

    def __init__(self, form):
        self._ids = set()
        self._refs = set()
        _collect(form, "id", self._ids)
        _collect(form, "ref", self._refs)

    def field_id(self):
        while True:
            candidate = "".join(secrets.choice(_ALPHABET) for _ in range(12))
            if candidate not in self._ids:
                self._ids.add(candidate)
                return candidate

    def ref(self):
        while True:
            candidate = str(uuid.uuid4())
            if candidate not in self._refs:
                self._refs.add(candidate)
                return candidate


# --------------------------------------------------------------------------- #
# Field builders
# --------------------------------------------------------------------------- #
class FieldBuilder:
    def __init__(self, ids: IdFactory):
        self._ids = ids

    def _base(self, title, ftype, properties=None, validations=True):
        field = {
            "id": self._ids.field_id(),
            "title": title,
            "ref": self._ids.ref(),
            "properties": properties if properties is not None else {},
            "type": ftype,
        }
        if validations:
            field["validations"] = {"required": False}
        return field

    def statement(self, title):
        return self._base(
            title,
            "statement",
            properties={"button_text": "Continue", "hide_marks": False},
            validations=False,
        )

    def short_text(self, title):
        return self._base(title, "short_text")

    def long_text(self, title):
        return self._base(title, "long_text")

    def yes_no(self, title):
        return self._base(title, "yes_no")

    def date(self, title):
        return self._base(
            title, "date", properties={"separator": "/", "structure": "DDMMYYYY"}
        )

    def multiple_choice(self, title, labels):
        """A single-select choice field, matching the form's existing schema."""
        return self._base(
            title,
            "multiple_choice",
            properties={
                "randomize": False,
                "allow_multiple_selection": False,
                "allow_other_choice": False,
                "none_of_the_above": False,
                "vertical_alignment": True,
                "choices": [
                    {"id": self._ids.field_id(), "ref": self._ids.ref(), "label": label}
                    for label in labels
                ],
            },
        )

    def question(self, title):
        """Infer a sensible field type from a plain question title."""
        key = title.strip()
        if key in CHOICE_FIELDS:
            return self.multiple_choice(title, CHOICE_FIELDS[key])
        low = key.lower()
        gates = (
            "do you own",
            "add another property",
            "are there any expected future changes",
            "is there a sale involved",
        )
        if low.startswith(gates):
            return self.yes_no(title)
        if "notes" in low:
            return self.long_text(title)
        if "date" in low:
            return self.date(title)
        return self.short_text(title)


# Questions that must render as proper Typeform choice fields (title -> labels).
CHOICE_FIELDS = {
    "Current position of the sale": [
        "Not yet marketed",
        "On the market",
        "Offer received",
        "Offer accepted",
        "Contracts exchanged",
    ],
    "Are there any early repayment charges?": ["Yes", "No", "Not known"],
}


# The sections to add, expressed as plain titles.
NEW_SECTIONS = {
    "mortgage_costs": {"title": "Mortgage Costs (£)"},
    "additional_property": {
        "title": "Additional Property",
        "questions": [
            "Do you own any additional properties?",
            "Property 1 - Current estimated property value (£)",
            "Property 1 - Mortgage outstanding (£)",
            "Property 1 - Rental income (£)",
            "Property 1 - Rental income frequency",
            "Property 1 - Additional property notes",
            "Add another property?",
            "Property 2 - Current estimated property value (£)",
            "Property 2 - Mortgage outstanding (£)",
            "Property 2 - Rental income (£)",
            "Property 2 - Rental income frequency",
            "Property 2 - Additional property notes",
            "Add another property?",
            "Property 3 - Current estimated property value (£)",
            "Property 3 - Mortgage outstanding (£)",
            "Property 3 - Rental income (£)",
            "Property 3 - Rental income frequency",
            "Property 3 - Additional property notes",
        ],
    },
    "future_changes": {
        "title": "Future Changes",
        "questions": [
            "Are there any expected future changes to your circumstances?",
            "Future changes notes",
        ],
    },
    "sale_of_existing_property": {
        "title": "Sale of Existing Property",
        "questions": [
            "Is there a sale involved with this purchase?",
            "Current estimated property value (£)",
            "Mortgage outstanding (£)",
            "Current mortgage lender",
            "Current mortgage interest rate (%)",
            "Mortgage term remaining",
            "Current mortgage product expiry date",
            "Current position of the sale",
            "Are there any early repayment charges?",
            "Sale notes",
        ],
    },
    "monthly_budget": {
        "title": "Monthly Budget",
        "questions": [
            "What is your total monthly budget for mortgage and protection "
            "payments combined?"
        ],
    },
    "general_insurance": {
        "title": "General Insurance",
        "questions": [
            "Current GI provider",
            "GI renewal date",
            "Current premium paid (£)",
            "Premium frequency",
        ],
    },
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def find_index(fields, ref, title):
    """Locate a field by ref, falling back to an exact title match."""
    for i, f in enumerate(fields):
        if f.get("ref") == ref:
            return i
    for i, f in enumerate(fields):
        if f.get("title") == title:
            return i
    raise ValueError(f"Anchor field not found (ref={ref!r}, title={title!r})")


def skip_rule(field_ref, target_ref):
    """yes_no rule: on 'No' jump to target; 'Yes' falls through to the next field."""
    return {
        "type": "field",
        "ref": field_ref,
        "actions": [
            {
                "action": "jump",
                "details": {"to": {"type": "field", "value": target_ref}},
                "condition": {
                    "op": "is",
                    "vars": [
                        {"type": "field", "value": field_ref},
                        {"type": "constant", "value": False},
                    ],
                },
            }
        ],
    }


def nth_index(seq, predicate, n):
    """Return the index of the n-th (0-based) item for which predicate is true."""
    count = 0
    for i, item in enumerate(seq):
        if predicate(item):
            if count == n:
                return i
            count += 1
    raise IndexError("predicate matched fewer than n+1 items")


# --------------------------------------------------------------------------- #
# Core transformation
# --------------------------------------------------------------------------- #
def apply_modifications(form):
    ids = IdFactory(form)
    fb = FieldBuilder(ids)

    spec = NEW_SECTIONS

    # ---- build the new field objects -------------------------------------- #
    mortgage_costs = fb.short_text(spec["mortgage_costs"]["title"])

    ap = spec["additional_property"]
    ap_stmt = fb.statement(ap["title"])
    ap_questions = [fb.question(q) for q in ap["questions"]]
    ap_own = ap_questions[0]
    add1_i = nth_index(ap["questions"],
                       lambda q: q.lower().startswith("add another property"), 0)
    add2_i = nth_index(ap["questions"],
                       lambda q: q.lower().startswith("add another property"), 1)
    ap_add1 = ap_questions[add1_i]
    ap_add2 = ap_questions[add2_i]

    fc = spec["future_changes"]
    fc_stmt = fb.statement(fc["title"])
    fc_questions = [fb.question(q) for q in fc["questions"]]
    fc_yes_no = fc_questions[0]

    sale = spec["sale_of_existing_property"]
    sale_stmt = fb.statement(sale["title"])
    sale_questions = [fb.question(q) for q in sale["questions"]]
    sale_yes_no = sale_questions[0]

    mb = spec["monthly_budget"]
    mb_stmt = fb.statement(mb["title"])
    mb_questions = [fb.question(q) for q in mb["questions"]]

    gi = spec["general_insurance"]
    gi_stmt = fb.statement(gi["title"])
    gi_questions = [fb.question(q) for q in gi["questions"]]

    before_section_10 = (
        [mortgage_costs]
        + [ap_stmt] + ap_questions
        + [fc_stmt] + fc_questions
        + [sale_stmt] + sale_questions
        + [mb_stmt] + mb_questions
    )
    general_insurance_block = [gi_stmt] + gi_questions

    # ---- insert fields (higher index first to keep positions valid) ------- #
    fields = form["fields"]
    gi_at = find_index(fields, ADDITIONAL_SERVICES_REF, ADDITIONAL_SERVICES_TITLE)
    fields[gi_at:gi_at] = general_insurance_block
    s10_at = find_index(fields, SECTION_10_REF, SECTION_10_TITLE)
    fields[s10_at:s10_at] = before_section_10

    # ---- logic ------------------------------------------------------------- #
    logic = form.setdefault("logic", [])

    # (a) Connect existing flow: the mortgage purchase-info group used to jump
    #     straight to Section 10; retarget it to the first new field so the new
    #     sections are reached. (The remortgage group has no jump and already
    #     falls through into Mortgage Costs.)
    retargeted = False
    for rule in logic:
        if rule.get("ref") == PURCHASE_GROUP_REF:
            for action in rule.get("actions", []):
                to = action.get("details", {}).get("to", {})
                if action.get("action") == "jump" and to.get("value") == SECTION_10_REF:
                    to["value"] = mortgage_costs["ref"]
                    retargeted = True
    if not retargeted:
        raise RuntimeError("Could not retarget the mortgage purchase-info group jump")

    # (b) New conditional rules.
    logic.append(skip_rule(ap_own["ref"], fc_stmt["ref"]))    # own? No -> Future Changes
    logic.append(skip_rule(ap_add1["ref"], fc_stmt["ref"]))   # add another? No -> Future Changes
    logic.append(skip_rule(ap_add2["ref"], fc_stmt["ref"]))   # add another? No -> Future Changes
    logic.append(skip_rule(fc_yes_no["ref"], sale_stmt["ref"]))  # changes? No -> Sale
    logic.append(skip_rule(sale_yes_no["ref"], mb_stmt["ref"]))  # sale? No -> Monthly Budget
    # Monthly Budget and General Insurance always display -> no logic.

    return form


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate(original, updated):
    # Existing fields preserved unchanged.
    updated_by_ref = {f["ref"]: f for f in updated["fields"]}
    for f in original["fields"]:
        if updated_by_ref.get(f["ref"]) != f:
            raise AssertionError(f"existing field changed or missing: {f['ref']}")

    # settings / theme / metadata preserved.
    for key in ("theme", "settings", "welcome_screens", "thankyou_screens"):
        if original.get(key) != updated.get(key):
            raise AssertionError(f"{key} was modified")

    # Unique ids and refs across the whole form.
    ids, refs = set(), set()
    ids_list, refs_list = [], []
    _collect(updated["fields"], "id", ids)
    _collect(updated["fields"], "ref", refs)

    def _flat(obj, key, out):
        if isinstance(obj, dict):
            if isinstance(obj.get(key), str):
                out.append(obj[key])
            for v in obj.values():
                _flat(v, key, out)
        elif isinstance(obj, list):
            for v in obj:
                _flat(v, key, out)

    _flat(updated["fields"], "id", ids_list)
    _flat(updated["fields"], "ref", refs_list)
    if len(ids_list) != len(set(ids_list)):
        raise AssertionError("duplicate field/choice ids detected")
    if len(refs_list) != len(set(refs_list)):
        raise AssertionError("duplicate field/choice refs detected")

    # Logic rules attach to and jump to existing top-level fields.
    top_refs = {f["ref"] for f in updated["fields"]}
    original_targets = set()
    for rule in original.get("logic", []):
        for action in rule.get("actions", []):
            to = action.get("details", {}).get("to", {})
            if to.get("type") == "field":
                original_targets.add(to.get("value"))
    preexisting_dangling = original_targets - {f["ref"] for f in original["fields"]}

    for rule in updated.get("logic", []):
        if rule["ref"] not in top_refs:
            raise AssertionError(f"logic rule on unknown field {rule['ref']}")
        for action in rule.get("actions", []):
            to = action.get("details", {}).get("to", {})
            if to.get("type") == "field":
                target = to.get("value")
                if target not in top_refs and target not in preexisting_dangling:
                    raise AssertionError(f"logic jumps to unknown field {target}")

    # Count newly added top-level choice fields.
    original_field_refs = {f["ref"] for f in original["fields"]}
    choice_fields_added = sum(
        1
        for f in updated["fields"]
        if f["ref"] not in original_field_refs
        and f.get("type") == "multiple_choice"
    )

    # Warnings: pre-existing dangling jump targets are carried through untouched.
    warnings = [
        f"pre-existing logic jump target not found among top-level fields "
        f"(left untouched): {ref}"
        for ref in sorted(preexisting_dangling)
    ]

    return {
        "fields_total": len(updated["fields"]),
        "fields_added": len(updated["fields"]) - len(original["fields"]),
        "logic_rules_total": len(updated.get("logic", [])),
        "logic_rules_added": len(updated.get("logic", []))
        - len(original.get("logic", [])),
        "choice_fields_added": choice_fields_added,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as fh:
        form = json.load(fh)

    original = json.loads(json.dumps(form))  # deep copy for validation

    updated = apply_modifications(form)
    stats = validate(original, updated)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(updated, fh, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_FILE}")
    print(f"  fields: {stats['fields_total']} (+{stats['fields_added']} new)")
    print(f"  new choice fields: {stats['choice_fields_added']}")
    print(f"  logic rules: {stats['logic_rules_total']} "
          f"(+{stats['logic_rules_added']} new)")
    if stats["warnings"]:
        for warning in stats["warnings"]:
            print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
