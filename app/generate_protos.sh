#!/bin/sh
set -e

# generate API protos and grpc stuff
find proto -name '*.proto' | protoc -I proto \
  --plugin=protoc-gen-grpc_python=$(which grpc_python_plugin) \
  --include_imports --include_source_info \
  \
  --descriptor_set_out proxy/protos.pb \
  \
  --python_out=backend/src/proto \
  --grpc_python_out=backend/src/proto \
  \
  --python_out=media/src/proto \
  --grpc_python_out=media/src/proto \
  \
  --js_out="import_style=commonjs,binary:frontend/src" \
  --grpc-web_out="import_style=commonjs+dts,mode=grpcweb:frontend/src" \
  \
  $(xargs)

# create internal backend protos
cd backend && find proto -name '*.proto' | protoc \
  --python_out=src \
  $(xargs)

# fixup python3 relative imports with oneliner from
# https://github.com/protocolbuffers/protobuf/issues/1491#issuecomment-690618628
sed -i -E 's/^import.*_pb2/from . \0/' backend/src/proto/*.py media/src/proto/*.py

echo "OK"
