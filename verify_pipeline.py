"""Independently verify the committed dataset, evaluation and live deployment."""
import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def verify(url=None):
    config = json.loads(Path('config.json').read_text())
    raw = Path('dataset/train.csv').read_bytes()
    data = pd.read_csv('dataset/train.csv')
    digest = hashlib.sha256(raw).hexdigest()
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert os.environ.get('GIT_COMMIT', sha) == sha, 'Checkout SHA mismatch'
    x = data[config['features']].apply(pd.to_numeric, errors='coerce')
    y = data['label'].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=int(config['seed']), stratify=y)
    independent = Pipeline([
        ('impute', SimpleImputer(strategy='median')),
        ('scale', StandardScaler()),
        ('classifier', LogisticRegression(max_iter=700, random_state=int(config['seed']))),
    ])
    independent.fit(x_train, y_train)
    accuracy = round(float(accuracy_score(y_test, independent.predict(x_test))), 6)
    expected = dict(student_id=config['student_id'], accuracy=accuracy,
                    training_rows=len(data), model_version=digest[:12],
                    dataset_sha256=digest, git_sha=sha)
    actual = json.loads(Path('artifacts/metrics.json').read_text())
    assert actual == expected, f'Metrics mismatch: {actual} != {expected}'
    bundle = joblib.load('artifacts/model.joblib')
    assert bundle['features'] == config['features']
    assert len(bundle['model'].predict(x.head(5))) == 5
    if url:
        deadline = time.monotonic() + 45
        while True:
            try:
                with urllib.request.urlopen(url + '/metrics', timeout=3) as response:
                    served = json.load(response)
                assert served == expected, f'Live metrics mismatch: {served}'
                break
            except (OSError, AssertionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        records = data[config['features']].head(5).to_dict('records')
        request = urllib.request.Request(url + '/predict',
            data=json.dumps({'records': records}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            prediction = json.load(response)
        probabilities = bundle['model'].predict_proba(pd.DataFrame(records))[:, 1]
        assert prediction['predictions'] == (probabilities >= 0.5).astype(int).tolist()
        assert np.allclose(prediction['probabilities'], probabilities, atol=1e-6)
    evidence = dict(expected, independently_verified=True, deployment_verified=bool(url))
    Path('artifacts/verification.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    verify(parser.parse_args().url)
