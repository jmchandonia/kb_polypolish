FROM kbase/sdkbase2:python
MAINTAINER KBase Developer
# -----------------------------------------
# In this section, you can install any system dependencies required
# to run your App.  For instance, you could place an apt-get update or
# install line here, a git checkout to download code, or run any other
# installation scripts.

RUN echo "start building docker image"

RUN apt-get update \
    && apt-get -y --allow-unauthenticated install wget

WORKDIR /kb/module

RUN wget https://github.com/rrwick/Polypolish/releases/download/v0.5.0/polypolish-linux-x86_64-musl-v0.5.0.tar.gz \
    && tar xzf polypolish-linux-x86_64-musl-v0.5.0.tar.gz \
    && mv polypolish polypolish_insert_filter.py /usr/local/bin

# -----------------------------------------

COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module

RUN make all

ENTRYPOINT [ "./scripts/entrypoint.sh" ]

CMD [ ]
