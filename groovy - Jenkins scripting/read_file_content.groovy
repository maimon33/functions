// Compare content
if ( readFile('startstatus').trim() == "Failed" ) {
    println "File content is exactly 'Failed'"
}

// String contains


// make variable
def testlerIP = readFile('testler_private_ip').trim()

// Read multiple lines
new File("src/main/resources/fileContent.txt").eachLine { line ->
    println line
}