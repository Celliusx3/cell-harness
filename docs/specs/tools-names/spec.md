# The tools files are named for what they hold

## Problem

Three of the files at the top of the tools folder are named for a word a reader has to decode. The pipeline holds the tools one agent is shown each step; the definition is what one tool is, a shape that belongs beside the other shapes; the approval file holds the gate, a second word for the same thing, and the person's grants.

## What changes for you

Nothing a person sees changes. Every call runs as before, and every schema the model reads is the same.

How the code reads after it, with one example: a script calls the clock tool.

1. The clock is a `Tool`, built in its folder and registered with the tool service; what a tool is sits in the models folder with the other shapes.
2. The call asks the person's approvals whether it must wait, then runs.
3. The model's own calls come through the agent's toolset, which shows it its tools each step and refuses one it was not shown.

## Decisions

- The pipeline is the toolset, as the person chose: one agent's set of tools.
- The definition is a tool, in the models folder, as the person chose; the MCP code names the MCP library's own tool type apart.
- The approval gate is the approvals, as the person chose, the word the Approvals page uses; the set of tools that ask is named for that, in the tools code and the channels alike.
- Text a person reads, tool names in tests, and the chat gateway keep their words.

## Out of scope

- The approval gate as a word in the long-form docs' prose, where it names the idea rather than the class.

## How we will know it works

- The 1489 backend tests pass, and lint passes, after every ticket.
- Every tool's schema is byte-identical before and after.
- A search for each old class, module and helper name outside the specs finds nothing.
