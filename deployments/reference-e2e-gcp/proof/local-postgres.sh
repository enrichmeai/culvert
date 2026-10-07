#!/usr/bin/env bash
# A throwaway local PostgreSQL 16 for the proof harness (#232): one server, two databases
# (`culvert` for the control plane, `airflow` for Airflow's metadata), trust auth on localhost.
#
#   proof/local-postgres.sh start [DIR] [PORT]   # default DIR=/tmp/culvert-proof-pg PORT=55432
#   proof/local-postgres.sh stop  [DIR]
#
# Both are idempotent: starting a running server or stopping a stopped one does nothing. DIR must
# be somewhere the postgres user can reach (for example under /tmp), not under a private home.
#
# PG_BIN overrides where initdb and pg_ctl are (default /usr/lib/postgresql/16/bin). When run as
# root it runs the server as the `postgres` user, since PostgreSQL refuses to run as root.
set -euo pipefail

cmd=${1:?usage: local-postgres.sh start|stop [DIR] [PORT]}
dir=${2:-/tmp/culvert-proof-pg}
port=${3:-55432}
bin=${PG_BIN:-/usr/lib/postgresql/16/bin}

as_pg() {
  if [ "$(id -u)" = 0 ]; then runuser -u postgres -- "$@"; else "$@"; fi
}

case "$cmd" in
  start)
    if [ ! -f "$dir/PG_VERSION" ]; then
      mkdir -p "$dir"
      [ "$(id -u)" = 0 ] && chown postgres "$dir"
      as_pg "$bin/initdb" -D "$dir" -U postgres --auth=trust -E UTF8 --locale=C >/dev/null
    fi
    if as_pg "$bin/pg_ctl" -D "$dir" status >/dev/null 2>&1; then
      echo "already running"
    else
      rm -f "$dir/postmaster.pid"  # left behind if the machine stopped under a running server
      as_pg "$bin/pg_ctl" -D "$dir" -o "-p $port -k /tmp -c listen_addresses=localhost" \
        -l "$dir/server.log" -w start >/dev/null
    fi
    for db in culvert airflow; do
      as_pg "$bin/psql" -h localhost -p "$port" -U postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
        || as_pg "$bin/createdb" -h localhost -p "$port" -U postgres "$db"
    done
    echo "PostgreSQL 16 on localhost:$port (databases culvert, airflow); data in $dir"
    ;;
  stop)
    if as_pg "$bin/pg_ctl" -D "$dir" status >/dev/null 2>&1; then
      as_pg "$bin/pg_ctl" -D "$dir" -m fast stop >/dev/null
    fi
    echo "stopped"
    ;;
  *)
    echo "usage: local-postgres.sh start|stop [DIR] [PORT]" >&2
    exit 2
    ;;
esac
