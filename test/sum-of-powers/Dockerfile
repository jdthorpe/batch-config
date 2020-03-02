# USAGE: 
# docker build -t jdthorpe/super-batch-test-sum-of-powers:v1 .
# docker push jdthorpe/super-batch-test-sum-of-powers:v1

# DOCKER IMAGE TO START WITH
FROM python:3.7

# INSTALL DEPENDENCIES
RUN pip install --upgrade pip \
	&& pip install numpy joblib

# COPY THE WORKER FILE INTO THE DOCKER FILE
COPY task.py constants.py worker.py ./
