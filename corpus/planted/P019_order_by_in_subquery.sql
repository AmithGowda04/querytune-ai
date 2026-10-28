SELECT t.CustomerID, t.TotalDue FROM (SELECT TOP 100 PERCENT CustomerID, TotalDue FROM dbo.SalesOrderHeader ORDER BY TotalDue DESC) AS t;
