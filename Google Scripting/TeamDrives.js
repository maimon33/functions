function getGoogleTeamDrives() {
  
    try {
      
      var teamDrives = {},
          baseUrl = "https://www.googleapis.com/drive/v3/teamdrives",
          token = ScriptApp.getOAuthToken(),
          params = {
            pageSize: 10,
            fields: "nextPageToken,teamDrives(id,name)"
          };
      
      do {
        
        // Written by Amit Agarwal @labnol
        // Web: www.ctrlq.org
  
        var queryString = Object.keys(params).map(function(p) {
          return [encodeURIComponent(p), encodeURIComponent(params[p])].join("=");
        }).join("&amp;");
        
        var apiUrl = baseUrl + "?" + queryString;
        
        var response = JSON.parse(
          UrlFetchApp.fetch( apiUrl, {
            method: "GET",
            headers: {"Authorization": "Bearer " + token}
          }).getContentText());
        
        var TeamDrivesLength = response["teamDrives"].length;
  
        for (var i = 0; i < TeamDrivesLength; i++) {
          var TeamDriveName = response["teamDrives"][i]["name"]
          var TeamDriveId = response["teamDrives"][i]["id"]
          teamDrives[TeamDriveName] = TeamDriveId;
        }
        
        params.pageToken = response.nextPageToken;
        
      } while (params.pageToken);
      
      return teamDrives;
      
    } catch (f) {
      
      Logger.log(f.toString());
      
    }
    
    return false;
    
  }
  
  function CountTDriveFiles(TeamDriveId) {
    var TeamFiles;
    var Files;
    var TeamDriveID = TeamDriveId
    var Options = {corpora:'teamDrive',includeTeamDriveItems:true,supportsTeamDrives:true,teamDriveId:TeamDriveID};
    var count;
    var TotalSize=0;
    var FileID;
    var file;
    var i=0;
    
    TeamFiles = Drive.Files.list(Options);
    Logger.log(TeamFiles)
    Files = TeamFiles.items;
    count = Files.length;
  
    while (TeamFiles.nextPageToken){
      var NextPage = TeamFiles.nextPageToken;
      var Options2 = {corpora:'teamDrive',includeTeamDriveItems:true,supportsTeamDrives:true,teamDriveId:TeamDriveID,pageToken:NextPage};
      TeamFiles = Drive.Files.list(Options2);
      Files = TeamFiles.items;
      count = count+Files.length;
    }
    
    return "Number of Files in this TeamDrive is: "+count;
    //Logger.log("The size of this TeamDrive is: "+TotalSize);
    //Logger.log("i="+i);
  }
  
  function getReport () {
    var Drives = getGoogleTeamDrives()
    //var DrivesCount = Object.keys(Drives).length
    
    var DrivesList = [];
    for(var k in Drives) DrivesList.push(k+':'+Drives[k]);
    
    Logger.log(DrivesList)
    
    //for (var i = 0; i < DrivesCount; i++) {
    //  var TeamDriveName = response["teamDrives"][i]["name"]
    //  var TeamDriveId = response["teamDrives"][i]["id"]
    //  teamDrives[TeamDriveId] = TeamDriveName;
    //}
    
    //Logger.log(CountTDriveFiles('0AAyAOcWKmOWmUk9PVA'))
  }