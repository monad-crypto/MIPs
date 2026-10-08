"""
Tests for lint_mips.py.

Run with: python3 -m unittest discover scripts
"""

import tempfile
import unittest
from pathlib import Path

import lint_mips

EIP_COMMIT_LINK = "https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-170.md"

HEADERS = [
    ("mip", "3"),
    ("title", "Linear Memory"),
    ("description", "Redefine memory expansion cost to be linear"),
    ("author", "Random J. User (@random)"),
    ("discussions-to", "https://forum.monad.xyz/t/mip-3-linear-memory/362"),
    ("status", "Draft"),
    ("last-call-deadline", None),
    ("type", "Standards Track"),
    ("category", "Core"),
    ("created", "2026-01-01"),
    ("requires", None),
    ("withdrawal-reason", None),
]

BODY = """\
## Abstract

Builds on [MIP-1](./MIP-1.md) and [MRC-13](../MRCs/MRC-13.md).

## Specification

Implementations MUST expand memory linearly.

## Rationale

Linear costs are simpler to reason about.

## Test Cases

See `../assets/MIP-3/`.

## Security Considerations

None.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
"""


def document(body: str = BODY, **overrides: str | None) -> str:
    lines = []
    for name, default in HEADERS:
        value = overrides.get(name.replace("-", "_"), default)
        if value is not None:
            lines.append(f"{name}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


def with_abstract(text: str) -> str:
    return document(BODY.replace("## Specification", text + "\n\n## Specification"))


def with_rationale(text: str) -> str:
    return document(BODY.replace("## Test Cases", text + "\n\n## Test Cases"))


class LintTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "MIPs").mkdir()
        (self.root / "MRCs").mkdir()
        (self.root / "assets" / "MIP-3").mkdir(parents=True)
        (self.root / "LICENSE.md").write_text("CC0\n")
        (self.root / "MIPs" / "MIP-1.md").write_text("---\nmip: 1\n---\n")
        (self.root / "MRCs" / "MRC-13.md").write_text("---\nmip: 13\n---\n")
        (self.root / "MIPs" / "MIP-2.md").write_text("---\nmip: 2\n---\n")
        (self.root / "assets" / "MIP-3" / "diagram.svg").write_text("<svg/>\n")
        self.repo = lint_mips.Repo(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def lint(self, text: str, name: str = "MIPs/MIP-3.md") -> list[lint_mips.Finding]:
        path = self.root / name
        path.write_text(text)
        return lint_mips.DocumentLinter(path, self.repo).lint()

    def assertRule(self, rule: str, text: str, name: str = "MIPs/MIP-3.md", level: str = "error") -> None:
        findings = self.lint(text, name)
        self.assertIn(rule, [f.rule for f in findings if f.level == level], [f.text() for f in findings])

    def assertNoRule(self, rule: str, text: str, name: str = "MIPs/MIP-3.md") -> None:
        findings = self.lint(text, name)
        self.assertNotIn(rule, [f.rule for f in findings], [f.text() for f in findings])

    def assertClean(self, text: str, name: str = "MIPs/MIP-3.md") -> None:
        self.assertEqual([], [f.text() for f in self.lint(text, name)])


class PreambleTest(LintTestCase):
    def test_valid_document(self) -> None:
        self.assertClean(document())

    def test_title_length(self) -> None:
        self.assertRule("preamble-len-title", document(title="X" * 91))
        self.assertClean(document(title="X" * 90))

    def test_title_standard(self) -> None:
        self.assertRule("preamble-re-standard", document(title="Linear Memory Standard"))

    def test_title_own_number(self) -> None:
        self.assertRule("preamble-re-own-number", document(title="MIP-3 Linear Memory"))
        self.assertRule("preamble-re-own-number", document(description="Describes mip 3."))

    def test_title_undashed_reference(self) -> None:
        self.assertRule("preamble-re-dash", document(title="Follow Up to MIP 1"))

    def test_title_case(self) -> None:
        self.assertRule("preamble-title-case", document(title="Linear memory"), level="warning")
        self.assertClean(document(title="Linear Memory of the EVM"))
        self.assertClean(document(title="Page-ified Storage State"))
        self.assertClean(document(title="MONAD_NINE Network Upgrade"))

    def test_description_length(self) -> None:
        self.assertRule("preamble-len-description", document(description="X" * 141))

    def test_description_sentence_case(self) -> None:
        self.assertRule("preamble-description-case", document(description="redefine memory costs"), level="warning")

    def test_author_forms(self) -> None:
        self.assertClean(document(author="Random J. User (@random) <random@example.com>"))
        self.assertClean(document(author="(@random)"))
        self.assertClean(document(author="Category Labs (@category-labs)"))
        self.assertClean(document(author="Random (@random), Other J. User <other@example.com>, Third"))
        self.assertRule("preamble-author", document(author="Random J. User <random@example.com> (@random)"))

    def test_author_github_username_required(self) -> None:
        self.assertRule("preamble-author-github", document(author="Category Labs"))
        self.assertRule("preamble-author-github", document(author="Random J. User <random@example.com>"))

    def test_list_separator(self) -> None:
        self.assertRule("preamble-list", document(author="A (@a),B (@b)"))
        self.assertRule("preamble-list", document(requires="1,13"))

    def test_discussions_to(self) -> None:
        self.assertRule("preamble-url", document(discussions_to=""))
        self.assertRule("preamble-discussions-to", document(discussions_to="https://github.com/monad-crypto/MIPs/pull/5"))
        self.assertRule("preamble-discussions-to", document(discussions_to="https://www.reddit.com/r/monad/comments/1"))
        self.assertRule("preamble-discussions-to", document(discussions_to="https://example.com/t/1"), level="warning")

    def test_status_enum(self) -> None:
        self.assertRule("preamble-enum", document(status="Accepted"))

    def test_type_enum(self) -> None:
        self.assertRule("preamble-enum", document(type="Standard"))

    def test_category(self) -> None:
        self.assertRule("preamble-category", document(type="Informational", category="Core"))
        self.assertRule("preamble-req-category", document(type="Meta", category=None))
        self.assertRule("preamble-enum", document(category="Process"))
        self.assertClean(document(type="Meta", category="Process"))
        self.assertClean(document(type="Informational", category=None))

    def test_dates(self) -> None:
        self.assertRule("preamble-date", document(created="2026-1-1"))
        self.assertRule("preamble-date", document(created="2026-13-01"))
        self.assertRule("preamble-date", document(status="Last Call", last_call_deadline="soon"))

    def test_last_call_deadline_required(self) -> None:
        self.assertRule("preamble-req-last-call-deadline", document(status="Last Call"))
        self.assertClean(document(status="Last Call", last_call_deadline="2026-02-01"))

    def test_withdrawal_reason_required(self) -> None:
        self.assertRule("preamble-req-withdrawal-reason", document(status="Withdrawn"))
        self.assertClean(document(status="Withdrawn", withdrawal_reason="Superseded."))

    def test_requires(self) -> None:
        self.assertRule("preamble-requires-exists", document(requires="42"))
        self.assertRule("preamble-uint-list", document(requires="one"))
        self.assertClean(document(requires="1, 13"))

    def test_hardfork_requires(self) -> None:
        self.assertRule("preamble-req-requires", document(type="Meta", category="Hardfork"))
        self.assertClean(document(type="Meta", category="Hardfork", requires="1"))

    def test_header_order(self) -> None:
        text = document().replace("type: Standards Track\ncategory: Core", "category: Core\ntype: Standards Track")
        self.assertRule("preamble-order", text)

    def test_duplicate_header(self) -> None:
        self.assertRule("preamble-no-dup", document().replace("status: Draft\n", "status: Draft\nstatus: Draft\n"))

    def test_unknown_header(self) -> None:
        self.assertRule("preamble-unknown", document().replace("status: Draft\n", "status: Draft\nreviews-to: nobody\n"))

    def test_trim(self) -> None:
        self.assertRule("preamble-trim", document().replace("title: Linear", "title:  Linear"))
        self.assertRule("preamble-trim", document().replace("title: Linear Memory\n", "title: Linear Memory \n"))

    def test_yaml(self) -> None:
        self.assertRule("preamble-yaml", document(title="Memory: Linear"))
        self.assertRule("preamble-yaml", document(title="Yes"))

    def test_required_header(self) -> None:
        self.assertRule("preamble-req", document(description=None))
        self.assertRule("preamble-req", document(mip=None))

    def test_draft_file_name(self) -> None:
        self.assertClean(document(mip=None), name="MIPs/MIP-draft_linear_memory.md")
        self.assertRule("file-name", document(), name="MIPs/MIP-draft_linear_memory.md")
        self.assertRule("file-name", document(mip=None, category="MRC"), name="MIPs/MIP-draft_linear_memory.md")

    def test_file_name(self) -> None:
        self.assertRule("file-name", document(), name="MIPs/MIP-4.md")
        self.assertRule("file-name", document(category="MRC"))
        self.assertNoRule("file-name", document(category="MRC"), name="MRCs/MRC-3.md")

    def test_mip_1_body_is_not_checked(self) -> None:
        self.assertClean(document(body="Process text.\n", mip="1", type="Meta", category="Process"), name="MIPs/MIP-1.md")


class BodyTest(LintTestCase):
    def test_required_sections(self) -> None:
        self.assertRule("markdown-req-section", document(BODY.replace("## Rationale\n\nLinear costs are simpler to reason about.\n\n", "")))

    def test_test_cases_recommended_for_core(self) -> None:
        body = BODY.replace("## Test Cases\n\nSee `../assets/MIP-3/`.\n\n", "")
        self.assertRule("markdown-req-section", document(body), level="warning")
        self.assertNoRule("markdown-req-section", document(body, category="Interface"))

    def test_section_order(self) -> None:
        body = BODY.replace("## Specification", "## Rationale", 1).replace("## Rationale\n\nLinear", "## Specification\n\nLinear")
        self.assertRule("markdown-order-section", document(body))

    def test_duplicate_section(self) -> None:
        self.assertRule("markdown-section-dup", with_rationale("## Rationale\n\nAgain."))

    def test_section_name_case(self) -> None:
        body = BODY.replace("## Security Considerations", "## Security considerations")
        self.assertRule("markdown-section-name", document(body))
        self.assertNoRule("markdown-req-section", document(body))

    def test_copyright_text(self) -> None:
        self.assertRule("markdown-copyright", document(BODY.replace("via [CC0]", "via [CC-0]")))
        findings = self.lint(document(BODY.replace("via [CC0]", "via\u00a0[CC0]")))
        self.assertIn("non-breaking space", [f.message for f in findings if f.rule == "markdown-copyright"][0])
        self.assertClean(document(BODY + "\n[eip-170]: " + EIP_COMMIT_LINK + "\n"))

    def test_draft_placeholders(self) -> None:
        body = BODY.replace("Linear costs are simpler to reason about.", "TBD")
        self.assertRule("markdown-placeholder", document(body, status="Final"))
        self.assertClean(document(body, status="Review"))

    def test_html_comments(self) -> None:
        self.assertRule("markdown-html-comments", with_abstract("<!-- TODO: remove -->"))
        self.assertRule("markdown-html-comments", with_abstract("Text <!-- spanning\nlines --> more"))
        self.assertClean(with_abstract("```html\n<!-- in code -->\n```"))

    def test_heading_space(self) -> None:
        self.assertRule("markdown-headings-space", document(BODY.replace("## Abstract", "##Abstract")))

    def test_external_links(self) -> None:
        self.assertRule("markdown-rel-links", with_abstract("See [the thread](https://ethereum-magicians.org/t/eip-170/1)."))
        self.assertClean(with_abstract("See [EIP-170](https://eips.ethereum.org/EIPS/eip-170)."))
        self.assertRule("markdown-rel-links", with_abstract("See <https://example.com/paper>."))
        self.assertRule("markdown-rel-links", with_abstract("See [MIP-1](https://github.com/monad-crypto/MIPs/blob/main/MIPs/MIP-1.md)."))
        self.assertClean(with_abstract(f"See [EIP-170]({EIP_COMMIT_LINK})."))
        self.assertClean(with_abstract("See [RFC 2119](https://www.ietf.org/rfc/rfc2119.html)."))
        self.assertClean(with_abstract("See [MonadBFT](https://doi.org/10.48550/arXiv.2502.20692)."))
        self.assertClean(with_abstract("```\nhttps://example.com/in-code\n```"))

    def test_reference_style_links(self) -> None:
        self.assertRule("markdown-rel-links", with_abstract("See [EIP-170][eip].\n\n[eip]: https://ethereum-magicians.org/t/eip-170/1"))
        self.assertClean(with_abstract(f"See [EIP-170][eip].\n\n[eip]: {EIP_COMMIT_LINK}"))

    def test_relative_links(self) -> None:
        self.assertRule("markdown-rel-links", with_abstract("![Diagram](../assets/MIP-3/missing.png)"))
        self.assertClean(with_abstract("![Diagram](../assets/MIP-3/diagram.svg)"))
        self.assertClean(with_abstract("See [the rationale](#rationale)."))

    def test_first_reference_must_be_linked(self) -> None:
        unlinked = document(BODY.replace("[MIP-1](./MIP-1.md)", "MIP-1"))
        self.assertRule("markdown-link-first", unlinked)
        self.assertClean(with_abstract("MIP-1 again, unlinked, is fine."))
        self.assertClean(with_abstract("MIP-3 refers to this document."))
        self.assertClean(with_rationale("Also [this one](./MIP-2.md) and [that one][two] exist.\n\n[two]: ./MIP-2.md"))
        self.assertRule("markdown-link-first", document(BODY.replace("[MIP-1](./MIP-1.md)", "[MIP-1](../MRCs/MRC-13.md)")))
        self.assertRule("markdown-link-first", document(BODY.replace("[MIP-1](./MIP-1.md)", "[MIP-1](#abstract)")))

    def test_mip_and_mrc_prefixes(self) -> None:
        self.assertRule("markdown-mip-mrc", document(BODY.replace("[MRC-13](../MRCs/MRC-13.md)", "[MIP-13](../MRCs/MRC-13.md)")))
        self.assertRule("markdown-mip-mrc", document(BODY.replace("[MIP-1](./MIP-1.md)", "[MRC-1](./MIP-1.md)")))

    def test_undashed_references(self) -> None:
        self.assertRule("markdown-re-dash", with_abstract("MIP 1 is the process."))
        self.assertRule("markdown-re-dash", with_abstract("MIP1 is the process."))
        self.assertRule("markdown-re-dash", with_abstract("[mip-1](./MIP-1.md) is the process."))

    def test_unknown_proposal(self) -> None:
        self.assertRule("markdown-refs", with_abstract("[MIP-42](./MIP-42.md) does not exist."))

    def test_references_in_code_are_ignored(self) -> None:
        self.assertClean(document(BODY.replace("[MIP-1](./MIP-1.md)", "`MIP-1`")))
        self.assertClean(with_abstract("```\nMIP 42\n```"))

    def test_rfc2119_keywords(self) -> None:
        self.assertRule("markdown-rfc2119", with_rationale("Clients SHOULD NOT do this."))
        self.assertClean(with_rationale("The `MUST` keyword and `OPTIONAL_FLAG` are code."))
        self.assertClean(with_rationale("OPTIONAL_FLAG is a constant."))
        self.assertClean(with_rationale("Clients may do this."))


if __name__ == "__main__":
    unittest.main()
