def cleanCancelled = false
    
stage('Confirm not tests are running') {

    test_list = ["mobile-test", "Staging-API-regression", "staging-web-regression", "new-gestalt-test", "algo_stability"]
    
    for (test in test_list) {
        def job = Jenkins.instance.getItemByFullName(test)
        
        for (build in job.builds) {
            if (build.isBuilding()) { 
                cleanCancelled = true
                println build
                println "A test is running! Postponing Staging stop by 15 minutes"
                break
            }
            break
        }
    }

    def jobname = env.JOB_NAME
        
    def job = Jenkins.instance.getItemByFullName(jobname)
    
    for (build in job.builds) {
        if (!build.isBuilding()) { continue; }
        if (cleanCancelled) {
            println "Either Staging is Stopped or a Test is still running. Aborting!"
            build.doStop();
        }
    }
}