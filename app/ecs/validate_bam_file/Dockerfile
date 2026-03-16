FROM public.ecr.aws/debian/debian:bookworm

ARG TARGETPLATFORM
ARG SAMTOOLS_VERSION="1.22.1"
RUN \
    if [ "${TARGETPLATFORM#linux/}" = "arm64" ]; then \
      platform_url="aarch64";  \
    else \
      platform_url="x86_64"; \
    fi && \
    echo "Standard APT" 1>&2 && \
    apt update -yq && \
    apt upgrade -yq && \
    # Basics along with htslib/samtools deps \
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
      --output-document "samtools-${SAMTOOLS_VERSION}.tar.bz2" \
      "https://github.com/samtools/samtools/releases/download/${SAMTOOLS_VERSION}/samtools-${SAMTOOLS_VERSION}.tar.bz2" && \
    tar -xf "samtools-${SAMTOOLS_VERSION}.tar.bz2" && \
    ( \
      cd "samtools-${SAMTOOLS_VERSION}" && \
      ./configure \
        --enable-plugins \
        --prefix=/usr && \
      make all all-htslib && \
      make install install-htslib \
    ) && \
    rm -rf \
      "samtools-${SAMTOOLS_VERSION}" \
      "samtools-${SAMTOOLS_VERSION}.tar.bz2" && \
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
