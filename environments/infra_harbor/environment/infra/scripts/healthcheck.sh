#!/bin/bash
curl -sf http://localhost:5000/health || exit 1
