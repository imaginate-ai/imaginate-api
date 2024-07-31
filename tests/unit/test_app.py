import gridfs.grid_file
import mongomock.gridfs
import pytest

# Core libraries
import gridfs

# Imaginate modules
from imaginate_api.utils import str_to_bool, validate_id, search_id, build_result
from imaginate_api.app import create_app
from imaginate_api.schemas.image_info import ImageStatus


# Other
from werkzeug.exceptions import BadRequest, NotFound, HTTPException
from werkzeug.datastructures import FileStorage
from bson.objectid import ObjectId
from io import BytesIO
from http import HTTPStatus

# Mocking
from unittest.mock import patch
import mongomock  # NOTE: mongomock doesn't work well with sorting


# A struct class to convert a dictionary to a object
# This is useful since MongoDB uses attributes and does not support dictionary keys
class Struct:
  def __init__(self, **entries):
    self.__dict__.update(entries)


@pytest.fixture()
def client():
  app = create_app()
  app.config.update({"TESTING": True})
  return app.test_client()


@pytest.fixture
def mock_mongo_client():
  mock_mongo_client = mongomock.MongoClient()
  return mock_mongo_client


@pytest.fixture
def mock_data():
  mock_data = [
    {
      "_id": ObjectId(),
      "data": b"data",
      "filename": "sample",
      "type": "image/png",
      "date": i,
      "theme": "sample",
      "real": True,
      "status": "unverified",
    }
    for i in range(5)
  ]
  return mock_data


@pytest.fixture
def mock_db(mock_mongo_client, mock_data):
  mock_db = mock_mongo_client["imaginate_dev"]
  # mock_db.create_collection('fs.files').insert_many(mock_data)
  return mock_db


@pytest.fixture
def mock_fs(mock_db, mock_data):
  mongomock.gridfs.enable_gridfs_integration()
  mock_fs = gridfs.GridFS(mock_db)
  for entry in mock_data:
    mock_fs.put(**entry)
  return mock_fs


# Set up database before running tests
@pytest.fixture(autouse=True)
def setup(mock_db, mock_fs):
  with (
    patch("imaginate_api.date.routes.fs", mock_fs),
    patch("imaginate_api.image.routes.fs", mock_fs),
    patch("imaginate_api.image.routes.db", mock_db),
    patch("imaginate_api.utils.fs", mock_fs),
  ):
    yield


@pytest.mark.parametrize(
  "string, expected", [("true", True), ("false", False), ("foo", False)]
)
def test_str_to_bool(string, expected):
  assert str_to_bool(string) == expected


@pytest.mark.parametrize(
  "image_id, expected",
  [
    ("621f1d71aec9313aa2b9074c", ObjectId("621f1d71aec9313aa2b9074c")),
    ("621f1d71aec9313aa2b9074cd", BadRequest),
    ("", BadRequest),
    (None, BadRequest),
  ],
)
def test_validate_id(image_id, expected):
  if expected is BadRequest:
    with pytest.raises(HTTPException) as err:
      validate_id(image_id)
    assert err.errisinstance(expected)
  else:
    assert validate_id(image_id) == expected


def test_search_id_success(mock_data, mock_fs):
  for entry in mock_data:
    _id = entry["_id"]
    res = search_id(_id)
    assert res._id == _id


@pytest.mark.parametrize(
  "_id, expected",
  [("621f1d71aec9313aa2b9074cd", NotFound), ("", NotFound), (None, NotFound)],
)
def test_search_id_exception(_id, expected):
  with pytest.raises(HTTPException) as err:
    search_id(_id)
  assert err.errisinstance(expected)


# Not sure how to test this function since it just organizes data
def test_build_result():
  pass


# Not testing as this endpoint will likely be removed in future
def test_get_root_endpoint():
  pass


# Not testing as this endpoint will likely be removed in future
def test_get_image_read_all_endpoint():
  pass


def test_post_image_create_endpoint_success(client, mock_data):
  for entry in mock_data:
    entry["file"] = FileStorage(
      stream=BytesIO(entry["data"]),
      filename=entry["filename"],
      content_type=entry["type"],
    )
    res = client.post("/image/create", data=entry, content_type="multipart/form-data")
    assert res.json == build_result(
      res.json["url"].split("/")[-1],
      entry["real"],
      entry["date"],
      entry["theme"],
      entry["status"],
    )


@pytest.mark.parametrize(
  "data, expected",
  [
    ({}, HTTPStatus.BAD_REQUEST),
    (
      {
        "date": 0,
        "theme": "sample",
        "real": True,
        "status": "unverified",
        "file": FileStorage(
          stream=BytesIO(b"data"), filename="test.pdf", content_type="application/pdf"
        ),
      },
      HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    ),
  ],
)
def test_post_image_create_endpoint_exception(data, expected, client):
  res = client.post("/image/create", data=data, content_type="multipart/form-data")
  assert res.status_code == expected


# Not testing scenarios with exceptions as they have been tested by helper functions:
# validate_id, search_id
def test_get_image_read_endpoint(mock_data, client, mock_fs):
  for entry in mock_data:
    _id = entry["_id"]
    res = client.get(f"/image/read/{_id}")
    assert res.status_code == HTTPStatus.OK
    assert res.get_data() == entry["data"]


# Not testing scenarios with exceptions as they have been tested by helper functions:
# validate_id, search_id
def test_get_image_read_properties_endpoint(mock_data, client):
  for entry in mock_data:
    _id = entry["_id"]
    res = client.get(f"/image/read/{_id}/properties")
    assert res.status_code == HTTPStatus.OK
    assert res.json == build_result(
      _id, entry["real"], entry["date"], entry["theme"], entry["status"]
    )


def test_get_date_images_endpoint_success(mock_data, client):
  for entry in mock_data:
    _id = entry["_id"]
    res = client.get(f"/date/{entry['date']}/images")
    assert res.status_code == HTTPStatus.OK
    assert res.json == [
      build_result(_id, entry["real"], entry["date"], entry["theme"], entry["status"])
    ]


@pytest.mark.parametrize(
  "day, expected", [("abc", HTTPStatus.BAD_REQUEST), (0, HTTPStatus.OK)]
)
def test_get_date_images_endpoint_exception(day, expected, client):
  res = client.get(f"date/{day}/images")
  assert res.status_code == expected


# Tested differently since the endpoint involves sorting
def test_get_date_latest_endpoint_success(mock_data, client):
  with patch("imaginate_api.date.routes.fs.find") as mock_find:
    sorted_data = sorted(mock_data, key=lambda x: x["date"], reverse=True)
    data = iter([Struct(**entry) for entry in sorted_data])
    mock_find.return_value.sort.return_value.limit.return_value = data
    res = client.get("date/latest")
    assert res.status_code == HTTPStatus.OK
    assert res.json == {"date": sorted_data[0]["date"]}


# Tested differently since the endpoint involves sorting
def test_get_date_latest_endpoint_exception(client):
  with patch("imaginate_api.date.routes.fs.find") as mock_find:
    data = iter([])
    mock_find.return_value.sort.return_value.limit.return_value = data
    res = client.get("date/latest")
    assert res.status_code == HTTPStatus.NOT_FOUND


# Image Verification Endpoints


# Unsure how to test this effectively as its returns a Flask Template
def test_get_verification_portal_endpoint_success(client):
  res = client.get("/image/verification-portal")
  assert res.status_code == HTTPStatus.OK


def test_post_update_status_endpoint_success(client, mock_data):
  for entry in mock_data:
    _id = str(entry["_id"])
    data = {"_id": _id, "status": ImageStatus.VERIFIED.value}
    res = client.post(
      "/image/update-status", data=data, content_type="multipart/form-data"
    )
    assert res.status_code == HTTPStatus.OK
    assert res.json == {"_id": data["_id"]}


@pytest.mark.parametrize(
  "data, expected",
  [
    ({}, HTTPStatus.BAD_REQUEST),
    ({"_id": "bad_id", "status": ImageStatus.VERIFIED.value}, HTTPStatus.BAD_REQUEST),
    ({"_id": str(ObjectId()), "status": "bad_status"}, HTTPStatus.BAD_REQUEST),
  ],
)
def test_post_update_status_endpoint_exception(data, expected, client, mock_data):
  res = client.post(
    "/image/update-status", data=data, content_type="multipart/form-data"
  )
  assert res.status_code == expected
