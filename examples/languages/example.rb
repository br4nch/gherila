require 'json'
require 'open3'

installing = ARGV == ['install']
abort 'Expected install or no arguments.' unless ARGV.empty? || installing
command = if !installing && !ENV.fetch('GHERILA_PYTHON', '').empty?
  [ENV['GHERILA_PYTHON'], '-u', '-m', 'gherila']
elsif Gem.win_platform?
  ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    ENV.fetch('GHERILA_LAUNCHER') { File.expand_path('../../runtime/gherila.ps1', __dir__) }]
else
  ['/bin/sh', ENV.fetch('GHERILA_LAUNCHER') { File.expand_path('../../runtime/gherila.sh', __dir__) }]
end
command << 'install' if installing
request = ENV.fetch('GHERILA_REQUEST') {
  JSON.generate(id: 'example', platform: 'github', method: 'get_user', kwargs: { username: 'octocat' })
}
output, status = Open3.capture2(*command, stdin_data: installing ? '' : request + "\n")
abort "Gherila exited with #{status.exitstatus}" unless status.success?
response = JSON.parse(output)
abort JSON.generate(response['error']) if response.key?('error')
puts JSON.generate(installing ? response : response.fetch('result'))
