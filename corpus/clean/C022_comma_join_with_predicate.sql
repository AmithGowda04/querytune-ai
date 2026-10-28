SELECT c.CustomerID, t.Name FROM dbo.Customer c, dbo.Territory t WHERE c.TerritoryID = t.TerritoryID;
