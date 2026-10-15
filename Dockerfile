FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip python3-gmsh=4.12.1+ds1-1.1build2 calculix-ccx=2.21-1 libglu1-mesa libgl1 libglib2.0-0 ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements-native.txt /tmp/requirements-native.txt
RUN pip install --no-cache-dir -r /tmp/requirements-native.txt
WORKDIR /app
COPY . /app
ENTRYPOINT ["python", "-m", "gongzheng.cli"]
CMD ["--help"]
