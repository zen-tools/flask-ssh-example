# -*- coding: utf-8 -*-
import select
import paramiko

from io import StringIO
from . import app
from flask import render_template, request


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/execute')
def execute():
    def generate(command):
        with app.app_context():
            ssh_key = paramiko.RSAKey.from_private_key(
                StringIO(app.config['SSH_PRIV_KEY'].lstrip()))

            ssh_conn = paramiko.SSHClient()
            ssh_conn.set_missing_host_key_policy(
                paramiko.AutoAddPolicy())
            ssh_conn.connect(
                hostname=app.config['SSH_HOSTNAME'],
                username=app.config['SSH_USERNAME'],
                pkey=ssh_key)

            stdin, stdout, stderr = ssh_conn.exec_command(command)
            channel = stdout.channel

            # we do not need stdin.
            stdin.close()
            # indicate that we're not going to write to that channel anymore
            channel.shutdown_write()

            # read stdout/stderr in order to prevent read block hangs
            yield stdout.channel.recv(len(stdout.channel.in_buffer))

            # chunked read to prevent stalls
            while (not channel.closed or channel.recv_ready() or
                   channel.recv_stderr_ready()):
                # stop if channel was closed prematurely,
                # and there is no data in the buffers.
                got_chunk = False
                readq, _, _ = select.select([stdout.channel], [], [], 1)
                for c in readq:
                    if c.recv_ready():
                        yield stdout.channel.recv(len(c.in_buffer))
                        got_chunk = True
                    if c.recv_stderr_ready():
                        # make sure to read stderr to prevent stall
                        yield stderr.channel.recv_stderr(
                            len(c.in_stderr_buffer))
                        got_chunk = True

                """
                1) make sure that there are at least 2 cycles with no data
                   in the input buffers in order to not exit too early
                   (i.e. cat on a >200k file).
                2) if no data arrived in the last loop,
                   check if we already received the exit code
                3) check if input buffers are empty
                4) exit the loop
                """
                if (not got_chunk and
                   stdout.channel.exit_status_ready() and not
                   stderr.channel.recv_stderr_ready() and not
                   stdout.channel.recv_ready()):
                    # indicate that we're not going
                    # to read from this channel anymore
                    stdout.channel.shutdown_read()
                    # close the channel
                    stdout.channel.close()
                    # exit as remote side is finished
                    # and our bufferes are empty
                    break
            # close all the pseudofiles
            stdout.close()
            stderr.close()
            ssh_conn.close()

            yield "Exit code: " + str(stdout.channel.recv_exit_status()) + '\n'
    return app.response_class(
        generate(request.args.get('command')), mimetype='text/plain')
