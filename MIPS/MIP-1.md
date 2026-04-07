---
mip: 1
title: MIP Purpose and Guidelines
description: Guidelines and procedures for the Monad Improvement Proposal process
author: QEDK (@qedk)
discussions-to: https://forum.monad.xyz/t/mip-1-mip-purpose-and-guidelines
status: Draft
type: Meta
category: Process
created: 2026-02-24
---

## What is a MIP?

MIP stands for Monad Improvement Proposal. A MIP is a design document providing information to the Monad community, or describing a new feature for Monad or its processes or environment. The MIP should provide a concise technical specification of the feature and a rationale for the feature. The MIP author is responsible for building consensus within the community and documenting dissenting opinions.

## MIP Rationale

MIPs are the primary mechanism for proposing new features, for collecting community technical input on an issue, and for documenting the design decisions that have gone into Monad. Because MIPs are maintained as text files in a versioned repository, their revision history is the historical record of the feature proposal.

For Monad implementers, MIPs are a convenient way to track the progress of their implementation. Ideally, each implementation maintainer would list the MIPs that they have implemented. This will give end users a convenient way to know the current status of a given implementation or library.

## MIP Types

There are three types of MIP:

- A **Standards Track MIP** describes any change that affects most or all Monad implementations, such as: a change to the network protocol, a change in block or transaction validity rules, proposed application standards or conventions, or any change or addition that affects the interoperability of applications using Monad. Standards Track MIPs consist of a design document and, where applicable, a reference implementation. Furthermore, Standards Track MIPs can be broken down into the following categories:
    - **Core**: improvements requiring a consensus fork or changes to the execution or consensus layer that affect the protocol’s behavior. This includes changes to block validity rules, transaction processing, EVM extensions, MonadBFT consensus parameters, and other modifications relevant to core protocol development.
    - **Networking**: improvements to the peer-to-peer networking layer, block propagation mechanisms (such as RaptorCast), transaction dissemination, and other network protocol specifications.
    - **Interface**: improvements around client-level standards like JSON-RPC method names, contract ABIs, and other interface conventions shared between the execution and consensus components.
    - **MRC**: application-level standards and conventions, including contract standards such as token standards, name registries, URI schemes, library or package formats, and wallet formats. MRC stands for Monad Request for Comments.
- A **Meta MIP** describes a process surrounding Monad or proposes a change to (or an event in) a process. Meta MIPs are like Standards Track MIPs but apply to areas other than the Monad protocol itself. They may propose an implementation, but not to Monad’s codebase; they often require community consensus; unlike Informational MIPs, they are more than recommendations, and users are typically not free to ignore them. Examples include procedures, guidelines, changes to the decision-making process, changes to the tools or environment used in Monad development, and specifications for named network upgrades. Furthermore, Meta MIPs can be broken down into the following categories:
    - **Process**:  proposals related to procedures, guidelines, changes to the decision-making process, changes to the tools or environment used in Monad development, and specifications for the MIP process itself.
    - **Hardfork**: network upgrade Meta MIPs that specify the set of Standards Track MIPs included in a named network upgrade (such as `MONAD_NINE`), along with activation timestamps for each network (Monad Testnet, Monad Mainnet). Each Hardfork Meta MIP serves as the canonical record for a specific network upgrade.
- An **Informational MIP** describes a Monad design issue, or provides general guidelines or information to the Monad community, but does not propose a new feature. Informational MIPs do not necessarily represent Monad community consensus or a recommendation, so users and implementers are free to ignore Informational MIPs or follow their advice.

It is highly recommended that a single MIP contain a single key proposal or new idea. The more focused the MIP, the more successful it tends to be.

A MIP must meet certain minimum criteria. It must be a clear and complete description of the proposed enhancement. The enhancement must represent a net improvement. The proposed implementation, if applicable, must be solid and must not complicate the protocol unduly.

### Special Requirements for Core MIPs

If a **Core** MIP mentions or proposes changes to the EVM (Ethereum Virtual Machine) or Monad-specific EVM extensions, it should refer to instructions by their mnemonics and define the opcodes of those mnemonics at least once. A preferred way is the following:

```
REVERT (0xfd)
```

Because Monad’s execution and consensus layers are maintained as separate components, Core MIPs SHOULD clearly indicate which component(s) are affected: the execution daemon, the consensus daemon, or both.

### Network Upgrade Meta MIPs

Named network upgrades on Monad (such as `MONAD_NINE`) MUST be specified by a Meta MIP with category `Hardfork`. The network upgrade Meta MIP MUST list all included Standards Track MIPs and specify the activation timestamps for each network (Monad Testnet, Monad Mainnet). The network upgrade Meta MIP MUST use `requires` to reference all included MIPs.

## MIP Work Flow

### Shepherding a MIP

Parties involved in the process are you, the champion or *MIP author*, the [*MIP editors*](#mip-editors), and the *Monad Core Developers*.

Before you begin writing a formal MIP, you should vet your idea. Ask the Monad community first if an idea is original to avoid wasting time on something that will be rejected based on prior research. It is thus recommended to open a discussion thread on the Monad community forum to do this.

Once the idea has been vetted, your next responsibility will be to present (by means of a MIP) the idea to the reviewers and all interested parties, invite editors, developers, and the community to give feedback on the aforementioned channels. You should try and gauge whether the interest in your MIP is commensurate with both the work involved in implementing it and how many parties will have to conform to it. For example, the work required for implementing a Core MIP will be much greater than for an MRC and the MIP will need sufficient interest from the Monad client team. Negative community feedback will be taken into consideration and may prevent your MIP from moving past the Draft stage.

### Core MIPs

For Core MIPs, given that they require client implementations to be considered **Final** (see “MIP Process” below), you will need to either provide an implementation for clients or convince client teams to implement your MIP.

Because Monad uses a two-daemon architecture (a consensus daemon and an execution daemon), Core MIPs may require changes to one or both components. Authors SHOULD coordinate with the relevant teams accordingly.

The best way to get client implementers to review your MIP is to present it on a Monad Core Developers call. These calls serve as a way for client implementers to do three things. First, to discuss the technical merits of MIPs. Second, to gauge what will be implemented. Third, to coordinate MIP implementation for network upgrades.

These calls generally result in a “rough consensus” around what MIPs should be implemented. Social consensus gathering during the MIP process is critical, and provides the MIP author and stakeholders with signal that the proposed changes are agreeable within the ecosystem. This “rough consensus” rests on the assumptions that MIPs are not contentious enough to cause a network split and that they are technically sound.

*In short, your role as the champion is to write the MIP using the style and format described below, shepherd the discussions in the appropriate forums, and build community consensus around the idea.*

### MIP Process

The following is the standardization process for all MIPs in all tracks:

![MIP Status Diagram](../assets/MIP-1/process.jpg)

**Idea** - An idea that is pre-draft. This is not tracked within the MIP Repository.

**Draft** - The first formally tracked stage of a MIP in development. A MIP is merged by a MIP Editor into the MIP repository when properly formatted.

**Review** - A MIP Author marks a MIP as ready for and requesting Peer Review.

**Last Call** - This is the final review window for a MIP before it is moved to `Final`. A MIP enters `Last Call` when the specification is stable and the author opens a PR with a review end date (`last-call-deadline`), typically 14 days later. If this period results in necessary normative changes, the MIP will revert to `Review`.

**Final** - This MIP represents the final standard. A Final MIP exists in a state of finality and should only be updated to correct errata and add non-normative clarifications. A PR moving a MIP from Last Call to Final SHOULD contain no changes other than the status update. Any content or editorial proposed change SHOULD be separate from this status-updating PR and committed prior to it.

**Stagnant** - Any MIP in `Draft` or `Review` or `Last Call` if inactive for a period of 3 months or greater is moved to `Stagnant`. A MIP may be resurrected from this state by Authors or MIP Editors through moving it back to `Draft` or its earlier status. If not resurrected, a proposal may stay forever in this status.

> *MIP Authors are notified of any algorithmic change to the status of their MIP*

**Withdrawn** - The MIP Author(s) have withdrawn the proposed MIP. This state has finality and can no longer be resurrected using this MIP number. If the idea is pursued at a later date, it is considered a new proposal.

**Living** - A special status for MIPs that are designed to be continually updated and not reach a state of finality. This includes most notably MIP-1.

## What Belongs in a Successful MIP?

Each MIP should have the following parts:

- **Preamble** - RFC 822 style headers containing metadata about the MIP, including the MIP number, a short descriptive title (limited to a maximum of 44 characters), a description (limited to a maximum of 140 characters), and the author details. Irrespective of the category, the title and description should not include the MIP number. See [below](#mip-header-preamble) for details.

- **Abstract** - Abstract is a multi-sentence (short paragraph) technical summary. This should be a very terse and human-readable version of the specification section. Someone should be able to read only the abstract to get the gist of what this specification does.

- **Motivation** *(optional)* - A motivation section is critical for MIPs that want to change the Monad protocol. It should clearly explain why the existing protocol specification is inadequate to address the problem that the MIP solves. This section may be omitted if the motivation is evident.

- **Specification** - The technical specification should describe the syntax and semantics of any new feature. The specification should be detailed enough to allow competing, interoperable implementations for any of the current Monad platform components (execution, consensus, or others).

- **Rationale** - The rationale fleshes out the specification by describing what motivated the design and why particular design decisions were made. It should describe alternate designs that were considered and related work, e.g. how the feature is supported in other chains or prior art from Ethereum EIPs. The rationale should discuss important objections or concerns raised during discussion around the MIP.

- **Backwards Compatibility** *(optional)* - All MIPs that introduce backwards incompatibilities must include a section describing these incompatibilities and their consequences. The MIP must explain how the author proposes to deal with these incompatibilities. This section may be omitted if the proposal does not introduce any backward incompatibilities, but this section must be included if backward incompatibilities exist.

- **Test Cases** *(optional)* - Test cases for an implementation are mandatory for MIPs that are affecting consensus changes. Tests should either be inlined in the MIP as data (such as input/expected output pairs) or included in `../assets/MIP-###/<filename>`. This section may be omitted for non-Core proposals.

- **Reference Implementation** *(optional)* - An optional section that contains a reference or example implementation that people can use to assist in understanding or implementing this specification. This section may be omitted for all MIPs.

- **Security Considerations** - All MIPs must contain a section that discusses the security implications and considerations relevant to the proposed change. Include information that might be important for security discussions, surfaces risks, and can be used throughout the life-cycle of the proposal. E.g., include security-relevant design decisions, concerns, important discussions, implementation-specific guidance and pitfalls, an outline of threats and risks and how they are being addressed. MIP submissions missing the "Security Considerations" section will be rejected. A MIP cannot proceed to status "Final" without a Security Considerations discussion deemed sufficient by the reviewers.

- **Copyright Waiver** - All MIPs must be in the public domain. The copyright waiver MUST link to the license file and use the following wording: `Copyright and related rights waived via [CC0](../LICENSE.md).`

## MIP Formats and Templates

MIPs should be written in [Markdown](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet) format. There is a [template](https://github.com/monad-crypto/MIPs/blob/main/mip-template.md) to follow.

## MIP Header Preamble

Each MIP must begin with an [RFC 822](https://www.ietf.org/rfc/rfc822.html) style header preamble, preceded and followed by three hyphens (`---`). This header is also termed "front matter" by Jekyll. The headers must appear in the following order.

`mip`: *MIP number*

`title`: *The MIP title is a few words, not a complete sentence*

`description`: *Description is one full (short) sentence*

`author`: *The list of the author's or authors' name(s) and/or username(s), or name(s) and email(s). Details are below.*

`discussions-to`: *The URL pointing to the official discussion thread*

`status`: *Draft, Review, Last Call, Final, Stagnant, Withdrawn, Living*

`last-call-deadline`: *The date last call period ends on* (Optional field, only needed when status is `Last Call`)

`type`: *One of `Standards Track`, `Meta`, or `Informational`*

`category`: *One of `Core`, `Networking`, `Interface`, or `MRC` for `Standards Track` MIPs; one of `Process` or `Hardfork` for `Meta` MIPs* (Optional field, only needed for `Standards Track` and `Meta` MIPs)

`created`: *Date the MIP was created on*

`requires`: *MIP number(s)* (Optional field)

`withdrawal-reason`: *A sentence explaining why the MIP was withdrawn.* (Optional field, only needed when status is `Withdrawn`)

Headers that permit lists must separate elements with commas.

Headers requiring dates will always do so in the format of ISO 8601 (yyyy-mm-dd).

### `author` Header

The `author` header lists the names, email addresses or usernames of the authors/owners of the MIP. Those who prefer anonymity may use a username only, or a first name and a username. The format of the `author` header value must be:

> Random J. User &lt;address@dom.ain&gt;

or

> Random J. User (@username)

or

> Random J. User (@username) &lt;address@dom.ain&gt;

if the email address and/or GitHub username is included, and

> Random J. User

if neither the email address nor the GitHub username are given.

At least one author must use a GitHub username, in order to get notified on change requests and have the capability to approve or reject them.

### `discussions-to` Header

While a MIP is a draft, a `discussions-to` header will indicate the URL where the MIP is being discussed.

The preferred discussion URL is a topic on the Monad community forum. The URL cannot point to GitHub pull requests, any URL which is ephemeral, and any URL which can get locked over time (i.e. Reddit topics).

### `type` Header

The `type` header specifies the type of MIP: Standards Track, Meta, or Informational. If the track is Standards, please include the subcategory (Core, Networking, Interface, or MRC). If the track is Meta, please include the subcategory (Process or Hardfork).

### `category` Header

The `category` header specifies the MIP's category. This is required for Standards Track and Meta MIPs only.

### `created` Header

The `created` header records the date that the MIP was assigned a number. The header should be in yyyy-mm-dd format, e.g. 2025-11-24.

### `requires` Header

MIPs may have a `requires` header, indicating the MIP numbers that this MIP depends on. If such a dependency exists, this field is required.

A `requires` dependency is created when the current MIP cannot be understood or implemented without a concept or technical element from another MIP. Merely mentioning another MIP does not necessarily create such a dependency.

## Linking to External Resources

Other than the specific exceptions listed below, links to external resources SHOULD NOT be included. External resources may disappear, move, or change unexpectedly.

### Permitted External Resources

The following external resources may be linked:

- **MonadBFT Specification**: Links to the [MonadBFT specification](https://doi.org/10.48550/arXiv.2502.20692) may be included using normal Markdown syntax, but MUST anchor to a specific version.
- **Ethereum Yellow Paper**: Links to the [Ethereum Yellow Paper](https://github.com/ethereum/yellowpaper/blob/efc5f9a1f356cba376c978eedb63cb0363c2aa85/Paper.tex) may be included using normal Markdown syntax, but MUST anchor to a specific commit.
- **Ethereum Execution Client Specifications**: Links to the [Ethereum Execution Client Specifications](https://github.com/ethereum/execution-specs) may be included using normal Markdown syntax, but MUST anchor to a specific commit.
- **Internet Engineering Task Force (IETF)**: Links to an IETF Request For Comment (RFC) specification may be included using normal Markdown syntax. Permitted URLs MUST anchor to a specification with an assigned RFC number.
- **Ethereum Improvement Proposals (EIPs)**: Links to [EIPs](https://github.com/ethereum/EIPs) may be included using normal Markdown syntax, but MUST anchor to a specific commit.
- **Bitcoin Improvement Proposals (BIPs)**: Links to [BIPs](https://github.com/bitcoin/bips) may be included using normal Markdown syntax, but MUST anchor to a specific commit.
- **Chain Agnostic Improvement Proposals (CAIPs)**: Links to [CAIPs](https://github.com/ChainAgnostic/CAIPs) may be included using normal Markdown syntax, but MUST anchor to a specific commit.
- **World Wide Web Consortium (W3C)**: Links to a W3C “Recommendation” status specification may be included using normal Markdown syntax. Permitted URLs MUST anchor to a specification in the technical reports namespace with a date.
- **Digital Object Identifier System (DOI)**: Links qualified with a Digital Object Identifier (DOI) may be included. The top-level URL field must resolve to a copy of the referenced work that is freely accessible to the public.

## Linking to Other MIPs

References to other MIPs should follow the format `MIP-N` where `N` is the MIP number you are referring to. Each MIP that is referenced in a MIP MUST be accompanied by a relative markdown link the first time it is referenced, and MAY be accompanied by a link on subsequent references. The link MUST always be done via relative paths so that the links work in this GitHub repository, forks of this repository, and mirrors. For example, you would link to this MIP as `./MIP-1.md`.

When referring to a MIP with a `category` of `MRC`, it must be written in the hyphenated form `MRC-X` where `X` is that MIP’s assigned number. When referring to MIPs with any other `category`, it must be written in the hyphenated form `MIP-X` where `X` is that MIP’s assigned number.

## Auxiliary Files

Images, diagrams and auxiliary files should be included in a subdirectory of the `assets` folder for that MIP as follows: `assets/MIP-N` (where `N` is to be replaced with the MIP number). When linking to an image in the MIP, use relative links such as `../assets/MIP-1/image.png`. Prefer SVG diagrams, then PNG, and finally everything else.

## Transferring MIP Ownership

It occasionally becomes necessary to transfer ownership of MIPs to a new champion. In general, we’d like to retain the original author as a co-author of the transferred MIP, but that’s really up to the original author. A good reason to transfer ownership is because the original author no longer has the time or interest in updating it or following through with the MIP process, or is unreachable. A bad reason to transfer ownership is because you don’t agree with the direction of the MIP. We try to build consensus around a MIP, but if that’s not possible, you can always submit a competing MIP.

If you are interested in assuming ownership of a MIP, send a message asking to take over, addressed to both the original author and the MIP editor. If the original author doesn’t respond in a timely manner, the MIP editor will make a unilateral decision.

## MIP Editors

The current MIP editors are:

* Piotr Dobaczewski (@pdobacz)
* QEDK (@qedk)
* Bruce Collie (@Baltoli)
* Ken Camman (@kjcamann)

## MIP Editor Responsibilities

For each new MIP that comes in, an editor does the following:

- Read the MIP to check if it is ready: sound and complete. The ideas must make technical sense, even if they don’t seem likely to get to final status.
- The title should accurately describe the content.
- Check the MIP for language (spelling, grammar, sentence structure, etc.), markup (GitHub-flavored Markdown), and code style.

If the MIP isn’t ready, the editor will send it back to the author for revision, with specific instructions.

Once the MIP is ready for the repository, the MIP editor will:

- Assign a MIP number (generally incremental; editors can reassign if number sniping is suspected).
- Merge the corresponding [pull request](https://github.com/monad-crypto/MIPs/pulls).
- Send a message back to the MIP author with the next step.

The editors don’t pass judgment on MIPs. They merely do the administrative and editorial part.

## Style Guide

### Titles

The `title` field in the preamble:

- Should be in title case.
- Should not include the word "standard" or any variation thereof; and
- Should not include the MIP's number.

### Descriptions

The `description` field in the preamble:

- Should be in sentence case.
- Should not include the word "standard" or any variation thereof; and
- Should not include the MIP's number.

### MIP Numbers

When referring to a MIP with a `category` of `MRC`, it must be written in the hyphenated form `MRC-X` where `X` is that MIP's assigned number. When referring to MIPs with any other `category`, it must be written in the hyphenated form `MIP-X` where `X` is that MIP's assigned number.

### RFC 2119 and RFC 8174

MIPs are encouraged to follow [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html) for terminology and to insert the following at the beginning of the Specification section:

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119 and RFC 8174.

Do not use RFC 2119 keywords (all-caps SHOULD/MUST/etc.) outside of the Specification section.

## Relationship to Ethereum EIPs

Monad is EVM-compatible and shares substantial heritage with the Ethereum protocol. Where Monad adopts an Ethereum feature without modification, a MIP MAY reference the corresponding EIP directly rather than duplicating its specification in full. Where Monad diverges from Ethereum behavior or introduces Monad-specific extensions, a standalone MIP MUST be written to document the differences.

Network upgrades that activate a bundle of upstream Ethereum EIPs (such as EIPs from an Ethereum hard fork like Fusaka) SHOULD be tracked as a single Standards Track MIP specifying which EIPs are activated and any Monad-specific modifications, and then included in the corresponding network upgrade Meta MIP.

## History

This document was derived heavily from [Ethereum’s EIP-1](https://eips.ethereum.org/EIPS/eip-1) written by Martin Becze, Hudson Jameson, et al., which in turn was derived from [Bitcoin’s BIP-0001](https://github.com/bitcoin/bips) written by Amir Taaki, which in turn was derived from [Python’s PEP-0001](https://peps.python.org/). In many places text was simply copied and modified. The authors of those documents are not responsible for its use in the Monad Improvement Process, and should not be bothered with technical questions specific to Monad or the MIP process. Please direct all comments to the MIP editors.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
