SELECT a.CustomerID AS CustomerA, b.CustomerID AS CustomerB FROM dbo.Customer a JOIN dbo.Customer b ON a.TerritoryID = b.TerritoryID AND a.CustomerID < b.CustomerID;
