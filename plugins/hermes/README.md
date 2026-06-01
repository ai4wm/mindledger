# Hermes plugin

This plugin connects Hermes Agent to mindledger as a read-only memory provider.

It recalls relevant indexed memory before each model turn by running:

```bash
mind search <query> --json-output
```

## Install

For local development, symlink this directory into Hermes:

```bash
ln -sfn /home/ubuntu/mindledger/plugins/hermes/mindledger ~/.hermes/plugins/mindledger
hermes config set memory.provider mindledger
```

Optional config in `~/.hermes/config.yaml`:

```yaml
plugins:
  mindledger:
    command: mind
    collection: ms_workspace_a212559d
    provider: onnx
    top_k: 5
    timeout: 20
```

The first version is intentionally read-only. It does not write, move, or index
memory files.
