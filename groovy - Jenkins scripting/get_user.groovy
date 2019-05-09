try {
    def current_build_user = "${currentBuild.rawBuild.getCause(hudson.model.Cause$UserIdCause).userName}"
    println current_build_user
    if (current_build_user == "timer") {
        println "User: timer"
        } else {
            println "User: $current_build_user"
        }
} catch(err) {
    println "No User found 'def current_build_user' failed"
}