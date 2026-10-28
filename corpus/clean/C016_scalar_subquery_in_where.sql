SELECT ProductID, Name FROM dbo.Product WHERE ListPrice > (SELECT AVG(ListPrice) FROM dbo.Product);
