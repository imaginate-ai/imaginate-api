from flask import Blueprint, abort, jsonify, make_response, request, render_template
from imaginate_api.extensions import fs, db
from imaginate_api.schemas.image_info import ImageStatus
from imaginate_api.utils import str_to_bool, validate_id, search_id, build_result
from http import HTTPStatus
from base64 import b64encode

bp = Blueprint("image", __name__)


# GET /read: used for viewing all images
# This endpoint is simply for testing purposes
@bp.route("/read")
def read_all():
  content = ""
  for res in fs.find():
    content += f'<li><a href="read/{res._id}">{res.filename} - {res._id}</a></li>\n'
  return f"<ul>\n{content}</ul>"


# POST /create: used for image population
# TODO: Add a lot of validation to fit our needs
@bp.route("/create", methods=["POST"])
def upload():
  try:
    file = request.files["file"]
    date = int(request.form["date"])
    theme = request.form["theme"]
    real = str_to_bool(request.form["real"])
    status = ImageStatus.UNVERIFIED.value
  except (KeyError, TypeError, ValueError):
    abort(HTTPStatus.BAD_REQUEST, description="Invalid schema")
  if not (
    file.filename and file.content_type and file.content_type.startswith("image/")
  ):
    abort(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, description="Invalid file")

  _id = fs.put(
    file.stream.read(),
    filename=file.filename,
    type=file.content_type,
    date=date,
    theme=theme,
    real=real,
    status=status,
  )
  return jsonify(build_result(_id, real, date, theme, status))


# GET /read/<id>: used for viewing a specific image
@bp.route("/read/<id>")
def read(id):
  _id = validate_id(id)
  res = search_id(_id)
  response = make_response(res.read())
  response.headers.set("Content-Type", res.type)
  response.headers.set("Content-Length", f"{res.length}")
  return response


# GET /read/<id>: used for viewing a specific image
@bp.route("/read/<id>/properties")
def read_properties(id):
  _id = validate_id(id)
  res = search_id(_id)
  return jsonify(build_result(res._id, res.real, res.date, res.theme, res.status))


# DELETE /delete/<id>: used for deleting a single image
@bp.route("/<id>", methods=["DELETE"])
def delete_image(id):
  _id = validate_id(id)
  res = search_id(_id)

  res_real = getattr(res, "real", None)
  res_date = getattr(res, "date", None)
  res_theme = getattr(res, "theme", None)
  res_status = getattr(res, "status", None)

  info = build_result(res._id, res_real, res_date, res_theme, res_status)
  fs.delete(res._id)
  return info


# Image Verification Routes


# GET /image/verification-portal: returns HTML page for image verification
@bp.route("/verification-portal", methods=["GET"])
def verification_portal():
  obj = db["fs.files"].find_one({"status": ImageStatus.UNVERIFIED.value})
  if obj:
    grid_out = fs.find_one({"_id": obj["_id"]})
    data = grid_out.read()
    base64_data = b64encode(data).decode("ascii")
    return render_template(
      "verification_portal.html",
      id=str(obj["_id"]),
      img_found=True,
      img_src=base64_data,
    )
  return render_template("verification_portal.html", img_found=False)


# POST /image/update-status: used to mark images as verified / rejected
@bp.route("/update-status", methods=["POST"])
def update_status():
  status = request.form["status"]
  _id = validate_id(request.form["_id"])
  if status and status in ImageStatus:
    query_filter = {"_id": _id}
    update_operation = {"$set": {"status": status}}
    res = db["fs.files"].find_one_and_update(query_filter, update_operation)
    return jsonify({"_id": str(res["_id"])})
  else:
    abort(400, description="New status not received")


# DELETE /image/delete-rejected: used to delete all images marked as rejected, returns all deleted images
@bp.route("/delete-rejected", methods=["DELETE"])
def delete_rejected():
  filter = {"status": ImageStatus.REJECTED.value}
  results = db["fs.files"].delete_many(filter)
  return results, 200
