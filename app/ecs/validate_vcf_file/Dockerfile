FROM public.ecr.aws/ubuntu/ubuntu:noble

# Note means we must use ubuntu as base image for now
LABEL maintainer="Alexis Lucattini"

# For multiarch images
ARG TARGETPLATFORM

# Install dependencies and somalier
ARG HTSLIB_VERSION="1.22"
ARG BCFTOOLS_VERSION="1.22.1"

# Install dependencies, samtools and somalier
RUN \
  if [ "${TARGETPLATFORM#linux/}" = "arm64" ]; then \
    platform_url="aarch64";  \
  else \
    platform_url="x86_64"; \
  fi && \
  apt update -y -q && \
  apt upgrade -y -q && \
  # Basics along with bedtools / htslib/samtools deps \
  apt install -yq \
    build-essential \
    libz-dev \
    wget \
    curl \
    pigz \
    unzip \
    jq \
    python3 \
    git \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    xz-utils \
    libssl-dev \
    libncurses5-dev \
    libcurl4-openssl-dev \
    liblzma-dev \
    procps \
    libopenblas-dev \
    libgomp1 && \
  # Download + Install samtools \
  wget \
    --quiet \
    --output-document "bcftools-${BCFTOOLS_VERSION}.tar.bz2" \
    "https://github.com/samtools/bcftools/releases/download/${BCFTOOLS_VERSION}/bcftools-${BCFTOOLS_VERSION}.tar.bz2" && \
  tar -xf "bcftools-${BCFTOOLS_VERSION}.tar.bz2" && \
  ( \
    cd "bcftools-${BCFTOOLS_VERSION}" && \
    ./configure \
      --enable-plugins \
      --prefix=/usr && \
    make all all-htslib && \
    make install install-htslib \
  ) && \
  rm -rf \
    "bcftools-${BCFTOOLS_VERSION}" \
    "bcftools-${BCFTOOLS_VERSION}.tar.bz2" && \
  # Install AWS \
  wget \
    --quiet \
    --output-document "awscliv2.zip" \
    "https://awscli.amazonaws.com/awscli-exe-linux-${platform_url}.zip" && \
  unzip -q "awscliv2.zip" && \
  ./aws/install \
    --install-dir /usr/aws-cli \
    --bin-dir /usr/bin && \
  rm -rf "awscliv2.zip" "aws/"

# Copy the docker entrypoint to the docker container
COPY docker-entrypoint.sh docker-entrypoint.sh

# Make the docker entrypoint executable
RUN chmod +x "./docker-entrypoint.sh"

# Set the entrypoint as the docker entrypoint script
CMD [ "./docker-entrypoint.sh" ]
