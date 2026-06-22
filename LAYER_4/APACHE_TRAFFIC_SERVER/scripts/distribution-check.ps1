$counts = @{}
1..80 | ForEach-Object {
    $resp = Invoke-RestMethod -Uri "http://localhost:8088/" -Method Get
    $id = $resp.appId
    if (-not $counts.ContainsKey($id)) {
        $counts[$id] = 0
    }
    $counts[$id]++
}

$counts.GetEnumerator() | Sort-Object Name | Format-Table -AutoSize

