# Source Links

Source links connect a memory back to the place it came from.

The first implementation stores:

- `label`: human-readable source name.
- `kind`: source class, such as `mac-settings`, `mac-contacts`, `photos`, `social-account`, `file-history`, `browser`, or `manual`.
- `uri`: a local path, deep link, app URI, web URL, or future internal source reference.
- `open_hint`: optional guidance for a computer-use adapter.
- `metadata`: source-specific structured details.

## Mac examples

```json
{
  "label": "Contacts card",
  "kind": "mac-contacts",
  "uri": "x-apple-contacts://person/user-name",
  "open_hint": "Open Contacts and navigate to this person."
}
```

```json
{
  "label": "Recent project folder",
  "kind": "file-history",
  "uri": "file:///Users/me/Documents/projects/only-memories",
  "open_hint": "Reveal this folder in Finder."
}
```

```json
{
  "label": "Photos place cluster",
  "kind": "photos",
  "uri": "photos://local/place/berlin-2026",
  "open_hint": "Open Photos and inspect the Berlin place cluster."
}
```

The URI does not need to be universally openable on day one. It should be stable enough that an operator, MCP client, or computer-use adapter can resolve it later.
