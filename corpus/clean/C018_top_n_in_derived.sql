SELECT t.CustomerID, t.TotalDue FROM (SELECT TOP 10 CustomerID, TotalDue FROM dbo.SalesOrderHeader ORDER BY TotalDue DESC) AS t ORDER BY t.TotalDue DESC;
