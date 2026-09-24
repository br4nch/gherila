require 'json'
require 'open3'

python = ENV.fetch('GHERILA_PYTHON') { Gem.win_platform? ? 'python' : 'python3' }
request = ENV.fetch('GHERILA_REQUEST') {
  JSON.generate(id: 'example', platform: 'github', method: 'get_user', kwargs: { username: 'octocat' })
}
output, status = Open3.capture2(python, '-u', '-m', 'gherila', stdin_data: request + "\n")
abort "Gherila exited with #{status.exitstatus}" unless status.success?
response = JSON.parse(output)
abort JSON.generate(response['error']) if response.key?('error')
puts JSON.generate(response.fetch('result'))
