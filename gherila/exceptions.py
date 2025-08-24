class BaseError(Exception):
  pass

class Error(BaseError):
  def __init__(self: "Error", message: str):
    self.message: str = message
    super().__init__(message)