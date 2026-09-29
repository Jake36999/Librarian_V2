# Librarian: the Cowork plugin

The plugin makes Claude the Librarian for one vault. It holds no research logic: the MCP server
(`resource-librarian mcp`) enforces the tiers, the session phases and the vault's rules, and
the plugin supplies the skills, the commands and the clerk agent.

## Install

1. Install the package with its MCP extra, so `resource-librarian` is on the path:
   `pip install -e '.v2[mcp]'`.
2. Create a vault if you have none: `resource-librarian init <folder>`.
3. Set `LIBRARIAN_VAULT` to the vault's folder in the environment the host launches servers
   from (or launch the host from inside the vault).
4. Add this folder as a plugin.

The server runs at `contribute` tier: Claude can run sessions, stage and review, but decisions
reserved for a person (`answer`, accepting a workflow, a sweep's review) stay with the person,
through the CLI or V2's own app.

## The clerk

Description tasks are answered without the research conversation, in this order:

1. a clerk endpoint in the vault's `[clerk]` config (DeepInfra, OpenAI, LM Studio);
2. **MCP sampling**, when the host offers it: each task goes to the host's model with no
   conversation context;
3. the **`clerk` agent** here, which takes waiting tasks one at a time (`clerk_next`,
   `clerk_submit`) in its own context. The next review of the item uses its answers.

If none is available, tasks wait and the session says so.

## To confirm on your machine (M0 spike a)

- the host launches the stdio server and it finds the vault;
- the MCP tool names the clerk agent lists (`mcp__plugin_librarian_librarian__…`) match what
  the host shows;
- whether the host advertises `sampling`.
