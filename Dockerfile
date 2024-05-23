FROM kbase/sdkbase2:python
MAINTAINER KBase Developer
# -----------------------------------------
# In this section, you can install any system dependencies required
# to run your App.  For instance, you could place an apt-get update or
# install line here, a git checkout to download code, or run any other
# installation scripts.

RUN echo "start building docker image"

WORKDIR /kb/module

# need to move from stretch to buster

RUN echo "deb http://deb.debian.org/debian buster main contrib" > /etc/apt/sources.list

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 648ACFD622F3D138 0E98404D386FA1D9 DCC9EFBF77E11517

RUN apt-get update \
    && apt-get -y --allow-unauthenticated install wget bwa

WORKDIR /kb/module

RUN wget https://github.com/rrwick/Polypolish/releases/download/v0.6.0/polypolish-linux-x86_64-musl-v0.6.0.tar.gz \
    && tar xzf polypolish-linux-x86_64-musl-v0.6.0.tar.gz \
    && mv polypolish /usr/local/bin

# -----------------------------------------

COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module

RUN make all

ENTRYPOINT [ "./scripts/entrypoint.sh" ]

CMD [ ]
