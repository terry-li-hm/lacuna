.PHONY: e2e

e2e:
	REG_ATLAS_NO_LLM=1 \
	DATA_DIR=/tmp/reg_atlas_data \
	CHROMA_PERSIST_DIR=/tmp/reg_atlas_data/db/chroma \
	PYTHONPATH=/Users/terry/code/reg-atlas \
	pytest tests/e2e_reg_atlas.py -q
