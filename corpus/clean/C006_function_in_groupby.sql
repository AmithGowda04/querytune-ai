SELECT YEAR(OrderDate) AS OrderYear, SUM(TotalDue) AS Revenue FROM dbo.SalesOrderHeader GROUP BY YEAR(OrderDate);
