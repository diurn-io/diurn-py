"""Generate `src/diurn/_generated/models.py` from the API's OpenAPI document.

The wire layer is generated and committed (SPEC §7.1): one frozen dataclass
per object schema, a `Literal` alias per string enum, and a `from_json` on each
class that turns the server's JSON into those types. Dates (`format: date`)
become `datetime.date`; instants stay strings here, because the API writes them
with an IANA zone in brackets that the hand-written layer parses
(`diurn._instant`).

Standard library only, so regenerating needs nothing installed:

    python tools/generate.py              # rewrite the module
    python tools/generate.py --check      # exit 1 if it would change (CI)

Refresh `openapi.json` from the platform first:

    cargo run -p diurn-api -- --openapi > ../diurn-py/openapi.json
"""

from __future__ import annotations

import argparse
import json
import keyword
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / 'openapi.json'
OUT = ROOT / 'src' / 'diurn' / '_generated' / 'models.py'

Schema = dict[str, Any]
# A converter takes the Python expression for a raw JSON value and returns the
# expression that builds the typed value from it.
Convert = Callable[[str], str]


def identity(expr: str) -> str:
    return expr


def ref_name(ref: str) -> str:
    return ref.rsplit('/', 1)[-1]


def py_name(name: str) -> str:
    """A JSON key as a Python identifier: `from` becomes `from_`."""
    return f'{name}_' if keyword.iskeyword(name) else name


def camel(name: str) -> str:
    return ''.join(part.title() for part in name.split('_'))


@dataclass
class Field:
    name: str  # the JSON key
    annotation: str
    convert: Convert
    required: bool
    default: str  # used when not required: "None" or "()"


@dataclass
class Model:
    name: str
    doc: str
    fields: list[Field] = field(default_factory=list)


class Generator:
    def __init__(self, spec: Schema) -> None:
        self.schemas: dict[str, Schema] = spec['components']['schemas']
        self.enums: dict[str, list[str]] = {}
        self.models: dict[str, Model] = {}
        self.depth = 0  # names comprehension variables, so nesting cannot clash

    # --- types ---------------------------------------------------------------

    @staticmethod
    def nullable(s: Schema) -> tuple[Schema, bool]:
        """Strip `null` from a schema, saying whether it was there."""
        t = s.get('type')
        if isinstance(t, list) and 'null' in t:
            rest = [x for x in t if x != 'null']
            return {**s, 'type': rest[0] if len(rest) == 1 else rest}, True
        for key in ('oneOf', 'anyOf'):
            if key in s:
                options = [o for o in s[key] if o.get('type') != 'null']
                if len(options) == 1 and len(options) < len(s[key]):
                    return options[0], True
        return s, False

    def resolve(self, s: Schema, owner: str, prop: str) -> tuple[str, Convert]:
        """(annotation, converter) for a schema that is not null."""
        if '$ref' in s:
            name = ref_name(s['$ref'])
            if 'enum' in self.schemas[name]:
                return name, identity
            return name, lambda e: f'{name}.from_json({e})'
        if 'enum' in s:
            alias = f'{owner}{camel(prop)}'
            self.enums[alias] = list(s['enum'])
            return alias, identity
        t = s.get('type')
        if t == 'string':
            if s.get('format') == 'date':
                return 'datetime.date', lambda e: f'datetime.date.fromisoformat({e})'
            return 'str', identity
        if t in ('integer', 'number', 'boolean'):
            return {'integer': 'int', 'number': 'float', 'boolean': 'bool'}[t], identity
        if t == 'array':
            item_ann, item = self.resolve_maybe_null(s['items'], owner, prop)
            var = self.var()
            return f'tuple[{item_ann}, ...]', lambda e: f'tuple({item(var)} for {var} in {e})'
        if t == 'object' and 'additionalProperties' in s and not s.get('properties'):
            value = s['additionalProperties']
            if value is True or value == {}:
                return 'dict[str, Any]', lambda e: f'dict({e})'
            val_ann, val = self.resolve_maybe_null(value, owner, prop)
            var = self.var()
            return (
                f'dict[str, {val_ann}]',
                lambda e: f'{{k: {val(var)} for k, {var} in {e}.items()}}',
            )
        if t == 'object' and 'properties' in s:
            name = f'{owner}{camel(prop)}'
            self.model(name, s)
            return name, lambda e: f'{name}.from_json({e})'
        return 'Any', identity

    def resolve_maybe_null(self, s: Schema, owner: str, prop: str) -> tuple[str, Convert]:
        inner, null = self.nullable(s)
        ann, conv = self.resolve(inner, owner, prop)
        if not null:
            return ann, conv
        if conv is identity:
            return f'{ann} | None', identity
        return f'{ann} | None', lambda e: f'None if {e} is None else {conv(e)}'

    def var(self) -> str:
        self.depth += 1
        return f'x{self.depth}'

    # --- models --------------------------------------------------------------

    def properties(self, s: Schema) -> tuple[dict[str, Schema], set[str]]:
        """Properties and required keys, merging `allOf`."""
        if 'allOf' in s:
            props: dict[str, Schema] = {}
            required: set[str] = set()
            for part in s['allOf']:
                part = self.schemas[ref_name(part['$ref'])] if '$ref' in part else part
                p, r = self.properties(part)
                props.update(p)
                required |= r
            return props, required
        return dict(s.get('properties', {})), set(s.get('required', []))

    def model(self, name: str, s: Schema) -> None:
        if name in self.models:
            return
        # The first paragraph only: the rest of a description is often about
        # the server's implementation, which a client's reader does not need.
        doc = (s.get('description') or '').strip().split('\n\n')[0]
        model = Model(name, doc)
        self.models[name] = model
        props, required = self.properties(s)
        for key, prop in props.items():
            inner, null = self.nullable(prop)
            ann, conv = self.resolve(inner, name, key)
            if key in required and not null:
                model.fields.append(Field(key, ann, conv, True, ''))
            elif inner.get('type') == 'array' and not null:
                # An absent array is an empty one: the API omits `sessions`
                # on a day without them.
                model.fields.append(Field(key, ann, conv, False, '()'))
            else:
                model.fields.append(Field(key, f'{ann} | None', conv, False, 'None'))

    def run(self) -> str:
        for name in sorted(self.schemas):
            s = self.schemas[name]
            if 'enum' in s:
                self.enums[name] = list(s['enum'])
            else:
                self.model(name, s)
        return self.render()

    # --- output --------------------------------------------------------------

    def render(self) -> str:
        out = [
            '"""Generated from openapi.json by tools/generate.py. Do not edit."""',
            '',
            'from __future__ import annotations',
            '',
            'import datetime',
            'from dataclasses import dataclass',
            'from typing import Any, Literal',
            '',
            '__all__ = [',
        ]
        out += [f'    "{n}",' for n in sorted(self.enums) + sorted(self.models)]
        out += [']']
        for name in sorted(self.enums):
            values = ', '.join(json.dumps(v) for v in self.enums[name])
            out += ['', f'{name} = Literal[{values}]']
        for name in sorted(self.models):
            out += self.render_model(self.models[name])
        return '\n'.join(out).rstrip() + '\n'

    @staticmethod
    def render_model(m: Model) -> list[str]:
        lines = ['', '', '@dataclass(frozen=True, slots=True)', f'class {m.name}:']
        if m.doc:
            doc = m.doc.replace('\\', '\\\\').replace('"""', "'''")
            first, *rest = doc.split('\n')
            if rest:
                lines.append(f'    """{first}')
                lines += [f'    {r}'.rstrip() for r in rest]
                lines += ['    """', '']
            else:
                lines += [f'    """{first}"""', '']
        ordered = [f for f in m.fields if f.required] + [f for f in m.fields if not f.required]
        for f in ordered:
            tail = '' if f.required else f' = {f.default}'
            lines.append(f'    {py_name(f.name)}: {f.annotation}{tail}')
        if not ordered:
            lines.append('    pass')
        lines += [
            '',
            '    @classmethod',
            f'    def from_json(cls, data: dict[str, Any]) -> {m.name}:',
            '        return cls(',
        ]
        for f in ordered:
            key = json.dumps(f.name)
            if f.required:
                value = f.convert(f'data[{key}]')
            else:
                got = f'data.get({key})'
                empty = '()' if f.default == '()' else 'None'
                value = (
                    got
                    if f.convert is identity and f.default == 'None'
                    else f'{empty} if {got} is None else {f.convert(f"data[{key}]")}'
                )
            lines.append(f'            {py_name(f.name)}={value},')
        lines.append('        )')
        return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or '').split('\n\n')[0])
    parser.add_argument('--check', action='store_true', help='fail if the module would change')
    args = parser.parse_args()
    text = Generator(json.loads(SPEC.read_text())).run()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f'{OUT.relative_to(ROOT)} is stale: run python tools/generate.py', file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    print(f'wrote {OUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
