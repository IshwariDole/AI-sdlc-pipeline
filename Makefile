.PHONY: install demo test eval eval-compare api dashboard clean

install:
	python -m pip install -r requirements.txt

demo:
	python run_pipeline.py data/samples/sample_brs.md --velocity 25 --max-sprints 20

test:
	python tests/test_sprint_allocator.py
	python tests/test_pipeline_e2e.py
	python tests/test_eval_dataset.py

eval:
	python tools/eval_classifier.py

eval-compare:
	python tools/eval_classifier.py --compare mock groq gemini

api:
	uvicorn api.main:app --reload --port 8000

dashboard:
	streamlit run dashboard/app.py

clean:
	rm -rf outputs/*.json outputs/*.md outputs/*.csv outputs/*.docx outputs/*.db
	find . -name __pycache__ -type d -exec rm -rf {} +
