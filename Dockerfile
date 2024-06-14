FROM rockylinux:8.5

# Update and Install Vim, Git, and Python
RUN dnf update -y && \
    dnf install -y \
    vim \
    git \
    python3.11

# Set the timezone to New York
RUN ln -snf /usr/share/zoneinfo/America/New_York /etc/localtime && \
    echo "America/New_York" > /etc/timezone

# Create a non-root user named "appuser"
RUN useradd -m -s /bin/bash pydev

# Set the working directory to the home directory of the "appuser"
WORKDIR /home/pydev

# Change ownership of the working directory to "pydev"
RUN chown -R pydev:pydev /home/pydev

# Create dir for mounted folder
RUN mkdir /home/pydev/mr_transfer

# Switch to the non-root user
USER pydev

# Start bash shell by default
CMD ["/bin/bash"]
