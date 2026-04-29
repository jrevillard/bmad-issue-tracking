"""Shared fixtures for YAML workflow tests."""

import os
import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(__file__).parent.parent / "skills" / "bmad-issue-tracking-setup" / "assets" / "workflows"

VALID_STEP_TYPES = {"INCLUDE", "READ", "FILTER", "RUN", "OUTPUT", "WRITE", "CHECK", "LOOP", "SET", "STOP", "CD"}

ALL_VALID_FIELDS = {
    "INCLUDE", "READ", "FILTER", "RUN", "OUTPUT", "WRITE", "CHECK",
    "LOOP", "SET", "STOP", "CD",
    "EXTRACT", "STORE", "EXPECT_EXIT", "CAPTURE", "PLATFORM",
}

PREDEFINED_VARS = {
    "planning_artifacts",
    "implementation_artifacts",
    "project-root",
    "sep",
    "prd_key",
    "story_key",
    "epic_num",
    "story_num",
    "prd_branch",
    "story_branch",
    "platform",
    "git_platform",
    "branch_patterns",
}

# Regex: matches a top-level YAML step "- STEP_TYPE:" at column 0 or 2
STEP_RE = re.compile(r"^(\s*)- (\w+):\s*(.*)")


def _is_top_level_step(line, base_indent):
    """Check if a line is a top-level step (not nested inside CHECK/LOOP)."""
    m = STEP_RE.match(line)
    if not m:
        return None
    indent = len(m.group(1))
    # Top-level steps have the same or less indentation than the base
    if indent <= base_indent:
        return m
    return None


def _parse_steps_from_lines(lines, base_indent=0):
    """Parse top-level steps from raw YAML lines.

    Args:
        lines: list of raw YAML lines
        base_indent: expected indentation for top-level steps (0 for root, 2 for nested)

    Returns list of dicts, one per step. Each dict has:
      - 'type': the step type keyword
      - 'raw_value': the raw string value after the colon (first line only)
      - 'block': list of (indent, key, value) tuples for sub-fields
      - 'start_line': 0-based line number
    """
    steps = []
    i = 0
    while i < len(lines):
        m = _is_top_level_step(lines[i], base_indent)
        if m:
            step_type = m.group(2)
            raw_value = m.group(3).strip()
            start_line = i
            block = []
            i += 1
            # Collect sub-fields (indented under the step)
            while i < len(lines):
                line = lines[i]
                # Check for next top-level step
                next_m = _is_top_level_step(line, base_indent)
                if next_m and next_m.group(2) in {
                    "INCLUDE", "READ", "FILTER", "RUN", "OUTPUT", "WRITE",
                    "CHECK", "LOOP", "SET", "STOP", "CD",
                }:
                    break
                if not line.strip() or line.strip().startswith("#"):
                    i += 1
                    continue
                # Sub-field: "  KEY: value" (indented under the step)
                sub_m = re.match(r"^(\s+)(\w+):\s*(.*)", line)
                if sub_m:
                    sub_indent = len(sub_m.group(1))
                    block.append((sub_indent, sub_m.group(2), sub_m.group(3).strip()))
                    i += 1
                    # Collect continuation lines
                    while i < len(lines):
                        cl = lines[i]
                        if not cl.strip() or cl.strip().startswith("#"):
                            i += 1
                            continue
                        # New sub-field at same indent
                        nm = re.match(r"^(\s+)(\w+):", cl)
                        if nm and len(nm.group(1)) <= sub_indent:
                            break
                        # Next top-level step
                        next_m2 = _is_top_level_step(cl, base_indent)
                        if next_m2:
                            break
                        if block:
                            _, key, val = block[-1]
                            block[-1] = (sub_indent, key, val + "\n" + cl.rstrip())
                        i += 1
                else:
                    i += 1
            steps.append({
                "type": step_type,
                "raw_value": raw_value,
                "block": block,
                "start_line": start_line,
            })
        else:
            i += 1
    return steps


def _parse_branches(step, parent_base_indent):
    """Recursively parse CHECK TRUE/FALSE and LOOP do branches into children."""
    if step["type"] not in ("CHECK", "LOOP"):
        return
    children = {}
    branch_keys = {"TRUE", "FALSE"} if step["type"] == "CHECK" else {"do"}
    for _, key, value in step["block"]:
        if key not in branch_keys or not value:
            continue
        branch_lines = value.lstrip("\n").split("\n")
        branch_lines = [l for l in branch_lines if l.strip()]
        if not branch_lines:
            children[key] = []
            continue
        # Detect base indent from first step-like line
        branch_base_indent = parent_base_indent + 2
        for line in branch_lines:
            m = STEP_RE.match(line)
            if m:
                branch_base_indent = len(m.group(1))
                break
        parsed = _parse_steps_from_lines(branch_lines, branch_base_indent)
        for child_step in parsed:
            _parse_branches(child_step, branch_base_indent)
        children[key] = parsed
    step["children"] = children


def flatten_steps(steps):
    """Return all steps at all nesting levels, depth-first."""
    result = []
    for step in steps:
        result.append(step)
        if "children" in step:
            for branch_steps in step["children"].values():
                result.extend(flatten_steps(branch_steps))
    return result


def _step_to_dict(step):
    """Convert a parsed step into a dict suitable for extract_step_var_defs/refs.

    Structure mirrors what yaml.safe_load would produce for simple steps.
    For complex steps (Python blocks), only extracts the first-level fields.
    """
    d = {step["type"]: step["raw_value"]}
    for _, key, value in step["block"]:
        # Try to parse simple values
        if key in ("TRUE", "FALSE"):
            # Branch blocks — store as list of parsed sub-steps
            branch_lines = value.split("\n") if value else []
            # These are continuation lines, need to find the full block
            # For now, store as string — branch analysis done separately
            d[key] = value
        elif key == "EXTRACT":
            # Parse "  key: dotpath" lines
            extract = {}
            for eline in value.split("\n"):
                em = re.match(r"\s+(\w+):\s*(.*)", eline)
                if em:
                    extract[em.group(1)] = em.group(2).strip()
            d[key] = extract
        elif value.startswith("{") and value.endswith("}"):
            # Inline dict like { variable: name, value: ... }
            try:
                d[key] = yaml.safe_load(">" + "\n  " + value[1:-1])
            except Exception:
                d[key] = value
        else:
            d[key] = value
    return d


def load_all_workflows():
    """Load all YAML workflow files, keyed by relative path."""
    workflows = {}
    for yaml_file in sorted(WORKFLOWS_DIR.rglob("*.yaml")):
        rel = yaml_file.relative_to(WORKFLOWS_DIR)
        with open(yaml_file, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        steps = _parse_steps_from_lines(lines)
        for step in steps:
            _parse_branches(step, 0)
        workflows[str(rel)] = {
            "path": yaml_file,
            "rel": str(rel),
            "content": content,
            "lines": lines,
            "steps": steps,
        }
    return workflows


def load_workflow(rel_path):
    """Load a single workflow by relative path."""
    full = WORKFLOWS_DIR / rel_path
    with open(full, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    steps = _parse_steps_from_lines(lines)
    for step in steps:
        _parse_branches(step, 0)
    return {
        "path": full,
        "rel": rel_path,
        "content": content,
        "lines": lines,
        "steps": steps,
    }


def parse_contract_header(content):
    """Parse the contract comment block at the top of a sub-workflow file."""
    contract = {"purpose": "", "input_variables": [], "output_variables": [], "side_effects": ""}
    lines = content.split("\n")
    current_section = None
    for line in lines:
        stripped = line.strip().lstrip("#").strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("purpose:"):
            contract["purpose"] = stripped.split(":", 1)[1].strip()
            current_section = "purpose"
        elif lower.startswith("input variables"):
            current_section = "input"
        elif lower.startswith("output variables"):
            current_section = "output"
        elif lower.startswith("side effects:"):
            current_section = "side_effects"
            contract["side_effects"] = stripped.split(":", 1)[1].strip()
        elif current_section == "input" and stripped.startswith("-"):
            var_name = stripped.lstrip("-").strip()
            if ":" in var_name:
                var_name = var_name.split(":")[0].strip()
            contract["input_variables"].append(var_name)
        elif current_section == "output" and stripped.startswith("-"):
            var_name = stripped.lstrip("-").strip()
            if ":" in var_name:
                var_name = var_name.split(":")[0].strip()
            contract["output_variables"].append(var_name)
    return contract


def extract_var_references(value):
    """Extract all {variable_name} references from a string."""
    if not isinstance(value, str):
        return set()
    return set(re.findall(r"\{(\w+)", value))


def get_step_field(step_dict, field_name):
    """Get a field value from a step dict, handling various formats."""
    if field_name in step_dict:
        return step_dict[field_name]
    # Check in block
    if "block" in step_dict:
        for _, key, value in step_dict["block"]:
            if key == field_name:
                return value
    return None


def extract_step_var_defs(step):
    """Extract variables defined by a step."""
    defs = set()
    step_type = step["type"] if isinstance(step, dict) and "type" in step else None
    if step_type is None:
        return defs

    if step_type == "SET":
        raw = step.get("raw_value", "")
        # Parse "{ variable: name, value: ... }"
        m = re.search(r"variable:\s*(\w+)", raw)
        if m:
            defs.add(m.group(1))
    elif step_type == "FILTER":
        v = get_step_field(step, "store")
        if v:
            defs.add(v)
    elif step_type == "READ":
        extract = get_step_field(step, "EXTRACT")
        if isinstance(extract, dict):
            defs.update(extract.keys())
    elif step_type == "OUTPUT":
        v = get_step_field(step, "store")
        if v:
            defs.add(v)
    return defs


def extract_step_var_refs(step):
    """Extract all {variable} references from a step."""
    refs = set()
    step_type = step["type"] if isinstance(step, dict) and "type" in step else None
    if step_type is None:
        return refs

    if step_type == "INCLUDE":
        refs.update(extract_var_references(step.get("raw_value", "")))
    elif step_type == "READ":
        refs.update(extract_var_references(step.get("raw_value", "")))
    elif step_type == "RUN":
        refs.update(extract_var_references(step.get("raw_value", "")))
    elif step_type == "CHECK":
        refs.update(extract_var_references(step.get("raw_value", "")))
    elif step_type == "OUTPUT":
        v = get_step_field(step, "message")
        if v:
            refs.update(extract_var_references(v))
    elif step_type == "WRITE":
        for field in ("file", "content"):
            v = get_step_field(step, field)
            if v:
                refs.update(extract_var_references(v))
    elif step_type == "SET":
        raw = step.get("raw_value", "")
        m = re.search(r"value:\s*[\"']?([^\"'}]+)", raw)
        if m:
            refs.update(extract_var_references(m.group(1)))
    elif step_type == "LOOP":
        for field in ("items", "as"):
            v = get_step_field(step, field)
            if v:
                refs.update(extract_var_references(v))
    elif step_type == "FILTER":
        for field in ("source", "where"):
            v = get_step_field(step, field)
            if v:
                refs.update(extract_var_references(v))
    return refs


def get_step_platform(step):
    """Get PLATFORM annotation from a step, or None."""
    return get_step_field(step, "PLATFORM")


@pytest.fixture
def all_workflows():
    return load_all_workflows()
