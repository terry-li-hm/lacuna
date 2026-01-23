# RegAtlas CLI Quick Reference

## Installation

```bash
cd ~/reg-atlas
source .venv/bin/activate
```

## Usage

### Health Check
```bash
python -m cli.main health
```

### Upload Document
```bash
python -m cli.main upload <file> --jurisdiction "Hong Kong"

# Examples:
python -m cli.main upload data/documents/sample_hkma_capital.txt -j "Hong Kong"
python -m cli.main upload data/documents/sample_mas_liquidity.txt -j "Singapore"
```

### Query Documents
```bash
python -m cli.main query "What are capital requirements?"

# With jurisdiction filter:
python -m cli.main query "What are capital requirements?" --jurisdiction "Hong Kong"

# More results:
python -m cli.main query "AML requirements" --results 10
```

### Compare Jurisdictions
```bash
python -m cli.main compare "Hong Kong" "Singapore"
```

### List Documents
```bash
python -m cli.main list-docs
```

### System Stats
```bash
python -m cli.main stats
```

## Testing Local vs Production

### Local (when running ./run.sh):
```bash
python -m cli.main health --api-url http://localhost:8000
python -m cli.main upload file.txt -j "Hong Kong" --api-url http://localhost:8000
```

### Production (default):
```bash
# Uses https://reg-atlas.onrender.com automatically
python -m cli.main health
python -m cli.main upload file.txt -j "Hong Kong"
```

### Override via Environment Variable:
```bash
export REGATLAS_API_URL=http://localhost:8000
python -m cli.main health  # Will use localhost
```

## Quick Testing Workflow

```bash
# 1. Upload sample documents
python -m cli.main upload data/documents/sample_hkma_capital.txt -j "Hong Kong"
python -m cli.main upload data/documents/sample_mas_liquidity.txt -j "Singapore"

# 2. Check stats
python -m cli.main stats

# 3. Query
python -m cli.main query "What are the minimum capital requirements?"

# 4. Compare
python -m cli.main compare "Hong Kong" "Singapore"
```

Total time: **~30 seconds** for full test cycle!

## Features

- ✅ Beautiful colored output with Rich
- ✅ Progress indicators for uploads
- ✅ Formatted tables for results
- ✅ AI-generated summaries (via OpenRouter)
- ✅ Error handling with helpful messages
- ✅ Works with both local and deployed APIs
- ✅ Fast iteration (<5 seconds per command)

## Next Steps

To make `regatlas` available globally:

```bash
cd ~/reg-atlas
uv pip install -e .

# Then use anywhere:
regatlas health
regatlas upload file.pdf -j "Hong Kong"
```
