pipeline {
    agent any
    triggers { githubPush() }
    options {
        timestamps()
        timeout(time: 8, unit: 'MINUTES')
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }
    environment {
        DOCKERHUB_IMAGE = 'zulmir/sp23-bai-023-api'
        CONTAINER_NAME = 'sp23-bai-023-api'
    }
    stages {
        stage('Checkout committed data') {
            steps {
                script {
                    def revision = checkout scm
                    env.GIT_COMMIT = revision.GIT_COMMIT
                }
                sh 'test -s dataset/train.csv && git diff --exit-code -- dataset/train.csv'
            }
        }
        stage('Train and independently validate') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv .ci-venv
                    . .ci-venv/bin/activate
                    python -m pip install --disable-pip-version-check -q -r requirements.txt
                    export GIT_COMMIT=$(git rev-parse HEAD)
                    python train.py
                    python verify_pipeline.py
                    git diff --exit-code -- dataset/train.csv
                '''
            }
        }
        stage('Build and publish') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', usernameVariable: 'DOCKERHUB_USER', passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    sh '''
                        set -eu
                        set +x
                        export DOCKER_CONFIG=$(mktemp -d)
                        trap 'docker logout >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT
                        printf '%s' "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USER" --password-stdin
                        docker build --label org.opencontainers.image.revision="$GIT_COMMIT" -t "$DOCKERHUB_IMAGE:$GIT_COMMIT" -t "$DOCKERHUB_IMAGE:latest" .
                        docker push "$DOCKERHUB_IMAGE:$GIT_COMMIT"
                        docker push "$DOCKERHUB_IMAGE:latest"
                    '''
                }
            }
        }
        stage('Deploy and verify served model') {
            steps {
                sh '''
                    set -eu
                    docker rm -f "$CONTAINER_NAME" || true
                    docker run -d --name "$CONTAINER_NAME" --restart unless-stopped -p 8000:8000 "$DOCKERHUB_IMAGE:$GIT_COMMIT"
                    . .ci-venv/bin/activate
                    python verify_pipeline.py --url http://localhost:8000
                '''
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'artifacts/metrics.json,artifacts/verification.json', allowEmptyArchive: true
            emailext(
                to: 'qasimalik@gmail.com',
                from: 'mirzulqarnain333@gmail.com',
                subject: "SP23-BAI-023: ${currentBuild.currentResult} build ${env.BUILD_NUMBER}",
                body: """SP23-BAI-023 automated retraining: ${currentBuild.currentResult}
Commit: ${env.GIT_COMMIT}
Public image: https://hub.docker.com/r/zulmir/sp23-bai-023-api
Metrics: http://54.206.86.232:8000/metrics
Build: ${env.BUILD_URL}
Dataset digest, row count and independently verified accuracy are attached when available.
""",
                attachmentsPattern: 'artifacts/metrics.json,artifacts/verification.json'
            )
        }
    }
}
