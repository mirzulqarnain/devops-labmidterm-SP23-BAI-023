pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        skipDefaultCheckout(true)
    }

    environment {
        IMAGE_NAME = 'sp23-bai-023-api:latest'
        CONTAINER_NAME = 'sp23-bai-023-api'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv .ci-venv
                    . .ci-venv/bin/activate
                    python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Generate Dataset and Train Model') {
            steps {
                sh '''
                    . .ci-venv/bin/activate

                    python generate_dataset.py \
                        --config config.json \
                        --output dataset/train.csv \
                        --rows 300

                    GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse HEAD)}" python train.py
                '''
            }
        }

        stage('Validate Training Results') {
            steps {
                sh '''
                    . .ci-venv/bin/activate

                    python -c "
import json
from pathlib import Path

metrics = json.loads(Path('artifacts/metrics.json').read_text())

assert metrics['student_id'] == 'SP23-BAI-023'
assert metrics['training_rows'] == 300
assert metrics['accuracy'] > 0
assert metrics['git_sha'] != 'local'
assert Path('artifacts/model.joblib').exists()

print('Training validation passed:', metrics)
"
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t $IMAGE_NAME .'
            }
        }

        stage('Deploy on EC2') {
            steps {
                sh '''
                    docker stop $CONTAINER_NAME || true
                    docker rm $CONTAINER_NAME || true

                    docker run -d \
                        --name $CONTAINER_NAME \
                        --restart unless-stopped \
                        -p 8000:8000 \
                        $IMAGE_NAME
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    sleep 5

                    curl --fail http://localhost:8000/health
                    echo ""

                    curl --fail http://localhost:8000/metrics
                    echo ""

                    curl --fail -X POST http://localhost:8000/predict \
                        -H "Content-Type: application/json" \
                        -d '{"records":[{"basket_volatility":0.5,"stock_gap":0.3,"promotion_load":0.7,"delivery_delay":0.2}]}'

                    echo ""
                '''
            }
        }
    }

    post {
        success {
            echo 'ML pipeline completed and application deployed successfully.'
        }

        failure {
            echo 'ML pipeline failed. Check the Jenkins console output.'
        }
    }
}
