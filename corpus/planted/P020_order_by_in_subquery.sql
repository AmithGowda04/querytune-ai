WITH ranked AS (SELECT TOP 100 PERCENT ProductID, ListPrice FROM dbo.Product ORDER BY ListPrice DESC) SELECT ProductID, ListPrice FROM ranked WHERE ListPrice > 100;
