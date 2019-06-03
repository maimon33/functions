import hudson.model.Node
import jenkins.model.Jenkins

Jenkins jenkins = Jenkins.instance
for (Node node in jenkins.nodes) {
  for (item in NAME_REGEX.split(',')) {
      if (node.nodeName.contains(item)) {
          println "Terminating: $node.nodeName"
          node.computer.doDoDelete()
      }
  }
}