SELECT COUNT(DISTINCT h.CustomerID) AS ActiveCustomers FROM dbo.SalesOrderHeader h JOIN dbo.Customer c ON c.CustomerID = h.CustomerID WHERE c.TerritoryID = 5;
