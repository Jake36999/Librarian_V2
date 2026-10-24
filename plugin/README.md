# Librarian: the Cowork plugin

The plugin makes Claude the Librarian for one vault. It holds no research logic: the MCP server
(`resource-librarian mcp`) forwards every call to the vault's running Librarian Core, which
enforces the tiers, the session phases and the vault's rules through the same writer, index and
document leases as Librarian's own window. The plugin supplies the skills, the commands and the
clerk agent.

## Install

1. Install the package with its MCP extra, so `librarian` (or the compatibility
   alias `resource-librarian`) is on the path: `pip install -e '.[mcp]'` from
   the `Librarian_V2` checkout, or install a Librarian release bundle.
2. Create a vault if you have none: `resource-librarian init <folder>`.
3. Set `LIBRARIAN_VAULT` to the vault's folder in the environment the host launches servers
   from (or launch the host from inside the vault).
4. Add this folder as a plugin.
5. Open Librarian for that vault (or start it from the tray). The MCP server never opens the
   vault itself: with no running Core, every call is refused with `CORE_REQUIRED`.

The server runs at `contribute` tier, and never above it: Claude can run sessions, stage and
review, but decisions reserved for a person (`answer`, accepting a workflow, a sweep's review)
stay with the person, through the CLI or V2's own app. A question for the person comes back to
Claude as the question; the person answers it in Librarian. Librarian's Modes setting applies
to Claude's writes too: in Ask, a write waits for the person in the Librarian window (choose
Auto to rely on the host's own approval prompts).

## The clerk

Description tasks are answered without the research conversation, in this order:

1. the Core's clerk: the Clerk position in Librarian, or a clerk endpoint in the vault's
   `[clerk]` config (DeepInfra, OpenAI, LM Studio);
2. the **`clerk` agent** here, which takes waiting tasks one at a time (`clerk_next`,
   `clerk_submit`) in its own context. The next review of the item uses its answers.

(MCP sampling is not used: calls run in the Core, which cannot call back into the host.)

If none is available, tasks wait and the session says so.

## To confirm on your machine (M0 spike a)

- the host launches the stdio server, it finds the vault, and Librarian is running for it;
- the MCP tool names the clerk agent lists (`mcp__plugin_librarian_librarian__…`) match what
  the host shows;
